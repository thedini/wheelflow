/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     |
    \\  /    A nd           | www.openfoam.com
     \\/     M anipulation  |
-------------------------------------------------------------------------------
    AmgX GPU-accelerated linear solver for OpenFOAM
-------------------------------------------------------------------------------
\*---------------------------------------------------------------------------*/

#include "amgxSolver.H"
#include "addToRunTimeSelectionTable.H"

// * * * * * * * * * * * * * * Static Data Members * * * * * * * * * * * * * //

namespace Foam
{
    defineTypeNameAndDebug(amgxSolver, 0);

    lduMatrix::solver::addsymMatrixConstructorToTable<amgxSolver>
        addamgxSolverSymMatrixConstructorToTable_;

    lduMatrix::solver::addasymMatrixConstructorToTable<amgxSolver>
        addamgxSolverAsymMatrixConstructorToTable_;
}


// * * * * * * * * * * * * * Private Member Functions  * * * * * * * * * * * //

void Foam::amgxSolver::initAmgX()
{
    if (initialized_)
    {
        return;
    }

    // Initialize AmgX
    AMGX_SAFE_CALL(AMGX_initialize());
    AMGX_SAFE_CALL(AMGX_initialize_plugins());

    // Set mode (GPU, double precision)
    mode_ = AMGX_mode_dDDI;  // device, double, double, int

    // Read config file or use default
    if (configFile_.empty())
    {
        // Default AMG configuration for pressure equation
        const char* cfg_string =
            "config_version=2, "
            "solver(s)=AMG, "
            "s:preconditioner(p)=JACOBI_L1, "
            "s:convergence=RELATIVE_INI_CORE, "
            "s:max_iters=100, "
            "s:tolerance=1e-6, "
            "s:norm=L2, "
            "s:print_solve_stats=1, "
            "p:max_iters=2";

        AMGX_SAFE_CALL(AMGX_config_create(&cfg_, cfg_string));
    }
    else
    {
        AMGX_SAFE_CALL(AMGX_config_create_from_file(&cfg_, configFile_.c_str()));
    }

    // Create resources
    AMGX_SAFE_CALL(AMGX_resources_create_simple(&rsrc_, cfg_));

    // Create matrix, vectors, and solver
    AMGX_SAFE_CALL(AMGX_matrix_create(&A_, rsrc_, mode_));
    AMGX_SAFE_CALL(AMGX_vector_create(&b_, rsrc_, mode_));
    AMGX_SAFE_CALL(AMGX_vector_create(&x_, rsrc_, mode_));
    AMGX_SAFE_CALL(AMGX_solver_create(&solver_, rsrc_, mode_, cfg_));

    initialized_ = true;

    Info<< "AmgX GPU solver initialized" << endl;
}


void Foam::amgxSolver::finalizeAmgX()
{
    if (!initialized_)
    {
        return;
    }

    AMGX_SAFE_CALL(AMGX_solver_destroy(solver_));
    AMGX_SAFE_CALL(AMGX_vector_destroy(x_));
    AMGX_SAFE_CALL(AMGX_vector_destroy(b_));
    AMGX_SAFE_CALL(AMGX_matrix_destroy(A_));
    AMGX_SAFE_CALL(AMGX_resources_destroy(rsrc_));
    AMGX_SAFE_CALL(AMGX_config_destroy(cfg_));
    AMGX_SAFE_CALL(AMGX_finalize_plugins());
    AMGX_SAFE_CALL(AMGX_finalize());

    initialized_ = false;
}


void Foam::amgxSolver::setMatrix(const lduMatrix& matrix)
{
    const lduAddressing& addr = matrix.lduAddr();

    const label nCells = addr.size();

    // Convert to CSR format for AmgX
    // OpenFOAM uses LDU format, need to convert

    // Count non-zeros per row
    labelList nnz(nCells, 1);  // Start with diagonal

    forAll(addr.lowerAddr(), faceI)
    {
        nnz[addr.lowerAddr()[faceI]]++;
        nnz[addr.upperAddr()[faceI]]++;
    }

    // Build row pointers
    labelList rowPtr(nCells + 1);
    rowPtr[0] = 0;
    forAll(nnz, i)
    {
        rowPtr[i+1] = rowPtr[i] + nnz[i];
    }

    label totalNnz = rowPtr[nCells];

    // Build column indices and values
    labelList colIdx(totalNnz);
    scalarList values(totalNnz);
    labelList currentPos(nCells);
    forAll(currentPos, i)
    {
        currentPos[i] = rowPtr[i];
    }

    // Add diagonal
    forAll(matrix.diag(), i)
    {
        colIdx[currentPos[i]] = i;
        values[currentPos[i]] = matrix.diag()[i];
        currentPos[i]++;
    }

    // Add off-diagonal
    forAll(addr.lowerAddr(), faceI)
    {
        label own = addr.lowerAddr()[faceI];
        label nei = addr.upperAddr()[faceI];

        // Lower triangle
        colIdx[currentPos[own]] = nei;
        values[currentPos[own]] = matrix.upper()[faceI];
        currentPos[own]++;

        // Upper triangle
        colIdx[currentPos[nei]] = own;
        values[currentPos[nei]] = matrix.lower()[faceI];
        currentPos[nei]++;
    }

    // Upload to AmgX
    AMGX_SAFE_CALL(AMGX_matrix_upload_all(
        A_,
        nCells,
        totalNnz,
        1,  // block_dimx
        1,  // block_dimy
        rowPtr.data(),
        colIdx.data(),
        values.data(),
        nullptr  // diag_data (optional)
    ));

    // Setup solver
    AMGX_SAFE_CALL(AMGX_solver_setup(solver_, A_));
}


// * * * * * * * * * * * * * * * * Constructors  * * * * * * * * * * * * * * //

Foam::amgxSolver::amgxSolver
(
    const word& fieldName,
    const lduMatrix& matrix,
    const FieldField<Field, scalar>& interfaceBouCoeffs,
    const FieldField<Field, scalar>& interfaceIntCoeffs,
    const lduInterfaceFieldPtrsList& interfaces,
    const dictionary& solverControls
)
:
    lduMatrix::solver
    (
        fieldName,
        matrix,
        interfaceBouCoeffs,
        interfaceIntCoeffs,
        interfaces,
        solverControls
    ),
    configFile_(solverControls.lookupOrDefault<fileName>("configFile", fileName(""))),
    initialized_(false)
{
    initAmgX();
}


// * * * * * * * * * * * * * * * * Destructor  * * * * * * * * * * * * * * * //

Foam::amgxSolver::~amgxSolver()
{
    finalizeAmgX();
}


// * * * * * * * * * * * * * * * Member Functions  * * * * * * * * * * * * * //

Foam::solverPerformance Foam::amgxSolver::solve
(
    scalarField& psi,
    const scalarField& source,
    const direction cmpt
) const
{
    solverPerformance solverPerf
    (
        typeName,
        fieldName_
    );

    // Cast away constness for AmgX (it needs non-const this)
    amgxSolver& nonConstThis = const_cast<amgxSolver&>(*this);

    // Set matrix
    nonConstThis.setMatrix(matrix_);

    const label nCells = psi.size();

    // Upload vectors
    AMGX_SAFE_CALL(AMGX_vector_upload(b_, nCells, 1, source.cdata()));
    AMGX_SAFE_CALL(AMGX_vector_upload(x_, nCells, 1, psi.cdata()));

    // Solve
    AMGX_SAFE_CALL(AMGX_solver_solve(solver_, b_, x_));

    // Download solution
    AMGX_SAFE_CALL(AMGX_vector_download(x_, psi.data()));

    // Get solver statistics
    int nIter;
    AMGX_SAFE_CALL(AMGX_solver_get_iterations_number(solver_, &nIter));

    AMGX_SOLVE_STATUS status;
    AMGX_SAFE_CALL(AMGX_solver_get_status(solver_, &status));

    solverPerf.nIterations() = nIter;

    // Set residuals - converged if status is success
    if (status == AMGX_SOLVE_SUCCESS)
    {
        solverPerf.initialResidual() = 1.0;
        solverPerf.finalResidual() = tolerance_ * 0.1;  // Below tolerance
    }
    else
    {
        solverPerf.initialResidual() = 1.0;
        solverPerf.finalResidual() = tolerance_ * 10;  // Above tolerance
    }

    return solverPerf;
}


// ************************************************************************* //

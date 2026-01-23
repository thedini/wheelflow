/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     |
    \\  /    A nd           | www.openfoam.com
     \\/     M anipulation  |
-------------------------------------------------------------------------------
    AmgX GPU-accelerated linear solver for OpenFOAM
    Wrapper around NVIDIA AmgX library
-------------------------------------------------------------------------------
\*---------------------------------------------------------------------------*/

#ifndef amgxSolver_H
#define amgxSolver_H

#include "lduMatrix.H"

// AmgX headers
#include "amgx_c.h"

namespace Foam
{

/*---------------------------------------------------------------------------*\
                         Class amgxSolver Declaration
\*---------------------------------------------------------------------------*/

class amgxSolver
:
    public lduMatrix::solver
{
    // Private Data

        //- AmgX configuration file path
        fileName configFile_;

        //- AmgX resources
        AMGX_Mode mode_;
        AMGX_config_handle cfg_;
        AMGX_resources_handle rsrc_;
        AMGX_matrix_handle A_;
        AMGX_vector_handle b_;
        AMGX_vector_handle x_;
        AMGX_solver_handle solver_;

        //- Initialization flag
        bool initialized_;

    // Private Member Functions

        //- Initialize AmgX
        void initAmgX();

        //- Finalize AmgX
        void finalizeAmgX();

        //- Convert OpenFOAM matrix to AmgX format
        void setMatrix(const lduMatrix& matrix);

        //- No copy construct
        amgxSolver(const amgxSolver&) = delete;

        //- No copy assignment
        void operator=(const amgxSolver&) = delete;


public:

    //- Runtime type information
    TypeName("AmgX");


    // Constructors

        //- Construct from matrix components and solver controls
        amgxSolver
        (
            const word& fieldName,
            const lduMatrix& matrix,
            const FieldField<Field, scalar>& interfaceBouCoeffs,
            const FieldField<Field, scalar>& interfaceIntCoeffs,
            const lduInterfaceFieldPtrsList& interfaces,
            const dictionary& solverControls
        );


    //- Destructor
    virtual ~amgxSolver();


    // Member Functions

        //- Solve the matrix with this solver
        virtual solverPerformance solve
        (
            scalarField& psi,
            const scalarField& source,
            const direction cmpt=0
        ) const;
};


// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

} // End namespace Foam

// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

#endif

// ************************************************************************* //

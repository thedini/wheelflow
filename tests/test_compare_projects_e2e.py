"""
End-to-end Playwright tests for Phase 4 features:
- US-005: Compare Simulation Runs
- US-006: Project Organization
"""

import pytest
import re
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="function")
def page(browser):
    """Create a new page for each test."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


class TestNavigationTabs:
    """Tests for new navigation tabs."""

    def test_compare_tab_exists(self, page: Page):
        """Test that Compare tab exists in navigation."""
        page.goto(BASE_URL)
        compare_btn = page.locator("[data-view='compare']")
        expect(compare_btn).to_be_visible()
        expect(compare_btn).to_have_text("Compare")

    def test_projects_tab_exists(self, page: Page):
        """Test that Projects tab exists in navigation."""
        page.goto(BASE_URL)
        projects_btn = page.locator("[data-view='projects']")
        expect(projects_btn).to_be_visible()
        expect(projects_btn).to_have_text("Projects")

    def test_click_compare_tab(self, page: Page):
        """Test clicking Compare tab shows compare view."""
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        compare_view = page.locator("#compare-view")
        expect(compare_view).to_be_visible()

    def test_click_projects_tab(self, page: Page):
        """Test clicking Projects tab shows projects view."""
        page.goto(BASE_URL)
        page.click("[data-view='projects']")

        projects_view = page.locator("#projects-view")
        expect(projects_view).to_be_visible()


class TestCompareView:
    """Tests for the Compare Simulations view (US-005)."""

    def test_compare_view_structure(self, page: Page):
        """Test that compare view has expected structure."""
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        # Header
        header = page.locator(".compare-header h2")
        expect(header).to_have_text("Compare Simulations")

        # Selection panel
        selection = page.locator(".compare-selection")
        expect(selection).to_be_visible()

        # Results panel
        results = page.locator(".compare-results")
        expect(results).to_be_visible()

    def test_compare_filters_exist(self, page: Page):
        """Test that compare filters are present."""
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        # Search input
        search = page.locator("#compare-search")
        expect(search).to_be_visible()

        # Quality filter
        quality = page.locator("#compare-quality-filter")
        expect(quality).to_be_visible()

        # Yaw filter
        yaw = page.locator("#compare-yaw-filter")
        expect(yaw).to_be_visible()

    def test_clear_compare_button_disabled_initially(self, page: Page):
        """Test that clear button is disabled when nothing is selected."""
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        clear_btn = page.locator("#clear-compare-btn")
        expect(clear_btn).to_be_disabled()

    def test_compare_job_list_loads(self, page: Page):
        """Test that job list area exists and renders."""
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        job_list = page.locator("#compare-job-list")
        expect(job_list).to_be_visible()

    def test_compare_empty_state_shows_instructions(self, page: Page):
        """Test that compare results show instructions when nothing selected."""
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        # Should show empty state with instructions
        empty_text = page.locator(".compare-table-container .empty-state h3")
        expect(empty_text).to_be_visible()

    def test_compare_functions_exist(self, page: Page):
        """Test that compare JavaScript functions are defined."""
        page.goto(BASE_URL)

        functions = [
            "loadCompareJobs",
            "filterCompareJobs",
            "clearCompareFilters",
            "toggleCompareJob",
            "clearComparison",
            "sortCompare"
        ]

        for func in functions:
            result = page.evaluate(f"typeof window.{func} === 'function'")
            assert result is True, f"Function {func} should be available"


class TestProjectsView:
    """Tests for the Project Organization view (US-006)."""

    def test_projects_view_structure(self, page: Page):
        """Test that projects view has expected structure."""
        page.goto(BASE_URL)
        page.click("[data-view='projects']")

        # Breadcrumb
        breadcrumb = page.locator(".projects-breadcrumb")
        expect(breadcrumb).to_be_visible()

        # New project button
        new_btn = page.locator("button:has-text('New Project')")
        expect(new_btn).to_be_visible()

    def test_projects_empty_state(self, page: Page):
        """Test that empty state is shown when no projects exist."""
        page.goto(BASE_URL)
        # Clear localStorage first
        page.evaluate("localStorage.removeItem('wheelflow_projects')")
        page.click("[data-view='projects']")

        empty_state = page.locator("#projects-empty")
        expect(empty_state).to_be_visible()

    def test_new_project_button_opens_modal(self, page: Page):
        """Test that clicking New Project opens modal."""
        page.goto(BASE_URL)
        page.click("[data-view='projects']")
        page.click("button:has-text('New Project')")

        modal = page.locator("#project-modal")
        expect(modal).to_be_visible()

    def test_project_modal_has_form_fields(self, page: Page):
        """Test that project modal has required form fields."""
        page.goto(BASE_URL)
        page.click("[data-view='projects']")
        page.click("button:has-text('New Project')")

        # Name field
        name_field = page.locator("#project-name")
        expect(name_field).to_be_visible()

        # Description field
        desc_field = page.locator("#project-description")
        expect(desc_field).to_be_visible()

        # Save button
        save_btn = page.locator("#project-modal button[type='submit']")
        expect(save_btn).to_be_visible()

    def test_project_modal_close(self, page: Page):
        """Test that project modal can be closed."""
        page.goto(BASE_URL)
        page.click("[data-view='projects']")
        page.click("button:has-text('New Project')")

        # Click cancel
        page.click("#project-modal button:has-text('Cancel')")

        modal = page.locator("#project-modal")
        expect(modal).to_have_class(re.compile(r"hidden"))

    def test_create_project(self, page: Page):
        """Test creating a new project."""
        page.goto(BASE_URL)
        page.evaluate("localStorage.removeItem('wheelflow_projects')")
        page.click("[data-view='projects']")
        page.click("button:has-text('New Project')")

        # Fill form
        page.fill("#project-name", "Test Project")
        page.fill("#project-description", "A test project description")

        # Submit
        page.click("#project-modal button[type='submit']")

        # Wait for modal to close
        page.wait_for_timeout(200)

        # Check project was created (localStorage)
        projects = page.evaluate("JSON.parse(localStorage.getItem('wheelflow_projects') || '[]')")
        assert len(projects) == 1
        assert projects[0]["name"] == "Test Project"

    def test_project_card_displays(self, page: Page):
        """Test that project cards display correctly."""
        page.goto(BASE_URL)

        # Create a project via localStorage
        page.evaluate("""
            localStorage.setItem('wheelflow_projects', JSON.stringify([{
                id: 'proj_test',
                name: 'Display Test',
                description: 'Testing display',
                jobIds: [],
                createdAt: new Date().toISOString()
            }]))
        """)

        page.click("[data-view='projects']")

        # Check card is visible
        card = page.locator(".project-card")
        expect(card).to_be_visible()

        # Check title
        title = page.locator(".project-card-title")
        expect(title).to_have_text("Display Test")

    def test_project_functions_exist(self, page: Page):
        """Test that project JavaScript functions are defined."""
        page.goto(BASE_URL)

        functions = [
            "loadProjects",
            "openProject",
            "closeProjectDetail",
            "showCreateProjectModal",
            "editProject",
            "closeProjectModal",
            "saveProject",
            "deleteProject",
            "showAssignModal",
            "closeAssignModal",
            "toggleJobAssignment",
            "removeFromProject"
        ]

        for func in functions:
            result = page.evaluate(f"typeof window.{func} === 'function'")
            assert result is True, f"Function {func} should be available"


class TestProjectBreadcrumb:
    """Tests for project breadcrumb navigation."""

    def test_breadcrumb_shows_all_projects(self, page: Page):
        """Test that initial breadcrumb shows All Projects."""
        page.goto(BASE_URL)
        page.click("[data-view='projects']")

        breadcrumb = page.locator(".breadcrumb-item.active")
        expect(breadcrumb).to_have_text("All Projects")

    def test_breadcrumb_updates_on_project_open(self, page: Page):
        """Test that breadcrumb updates when opening a project."""
        page.goto(BASE_URL)

        # Create a project
        page.evaluate("""
            localStorage.setItem('wheelflow_projects', JSON.stringify([{
                id: 'proj_nav_test',
                name: 'Navigation Test',
                description: '',
                jobIds: [],
                createdAt: new Date().toISOString()
            }]))
        """)

        page.click("[data-view='projects']")
        page.click(".project-card")

        # Breadcrumb should show project name
        breadcrumb = page.locator(".breadcrumb-item.active")
        expect(breadcrumb).to_have_text("Navigation Test")


class TestAssignModal:
    """Tests for the assign simulations modal."""

    def test_assign_modal_exists(self, page: Page):
        """Test that assign modal element exists."""
        page.goto(BASE_URL)

        modal = page.locator("#assign-modal")
        expect(modal).to_have_class(re.compile(r"hidden"))

    def test_close_assign_modal_function(self, page: Page):
        """Test that closeAssignModal function exists."""
        page.goto(BASE_URL)

        result = page.evaluate("typeof window.closeAssignModal === 'function'")
        assert result is True


class TestCompareTableSorting:
    """Tests for comparison table sorting functionality."""

    def test_sort_compare_function_exists(self, page: Page):
        """Test that sortCompare function exists."""
        page.goto(BASE_URL)

        result = page.evaluate("typeof window.sortCompare === 'function'")
        assert result is True

    def test_sort_compare_can_be_called(self, page: Page):
        """Test that sortCompare can be called without error."""
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        # Should not throw error even with no data
        page.evaluate("window.sortCompare('Cd')")
        page.evaluate("window.sortCompare('CdA')")
        page.evaluate("window.sortCompare('name')")


class TestCompareQualityFilter:
    """Tests for quality filter in comparison view."""

    def test_quality_filter_options(self, page: Page):
        """Test that quality filter has correct options."""
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        select = page.locator("#compare-quality-filter")

        # Check for options
        options = select.locator("option")
        texts = [options.nth(i).text_content() for i in range(options.count())]

        assert "All qualities" in texts
        assert "Basic" in texts
        assert "Standard" in texts
        assert "Pro" in texts


class TestProjectLocalStorage:
    """Tests for project localStorage persistence."""

    def test_projects_persist_in_localstorage(self, page: Page):
        """Test that created projects are saved to localStorage."""
        page.goto(BASE_URL)
        page.evaluate("localStorage.removeItem('wheelflow_projects')")
        page.click("[data-view='projects']")
        page.click("button:has-text('New Project')")

        page.fill("#project-name", "Persistent Project")
        page.click("#project-modal button[type='submit']")

        page.wait_for_timeout(200)

        # Reload page
        page.reload()
        page.click("[data-view='projects']")

        # Project should still exist
        card = page.locator(".project-card-title")
        expect(card).to_have_text("Persistent Project")

    def test_delete_project_removes_from_storage(self, page: Page):
        """Test that deleting a project removes it from localStorage."""
        page.goto(BASE_URL)

        # Create project via localStorage
        page.evaluate("""
            localStorage.setItem('wheelflow_projects', JSON.stringify([{
                id: 'proj_delete_test',
                name: 'Delete Me',
                description: '',
                jobIds: [],
                createdAt: new Date().toISOString()
            }]))
        """)

        page.click("[data-view='projects']")

        # Setup dialog handler before clicking delete
        page.on("dialog", lambda dialog: dialog.accept())

        # Click delete button
        page.click(".project-card-actions button[title='Delete']")

        page.wait_for_timeout(200)

        # Check localStorage
        projects = page.evaluate("JSON.parse(localStorage.getItem('wheelflow_projects') || '[]')")
        assert len(projects) == 0


class TestResponsiveLayout:
    """Tests for responsive layout of compare and projects views."""

    def test_compare_layout_desktop(self, page: Page):
        """Test compare layout at desktop width."""
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        layout = page.locator(".compare-layout")
        expect(layout).to_be_visible()

    def test_compare_layout_mobile(self, page: Page):
        """Test compare layout at mobile width."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.click("[data-view='compare']")

        layout = page.locator(".compare-layout")
        expect(layout).to_be_visible()

    def test_projects_layout_desktop(self, page: Page):
        """Test projects layout at desktop width."""
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(BASE_URL)
        page.click("[data-view='projects']")

        container = page.locator(".projects-container")
        expect(container).to_be_visible()

    def test_projects_layout_mobile(self, page: Page):
        """Test projects layout at mobile width."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.click("[data-view='projects']")

        container = page.locator(".projects-container")
        expect(container).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

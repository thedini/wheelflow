"""
Playwright E2E tests for WheelFlow UI

Tests the browser-based UI functionality including:
- Page load and rendering
- Navigation between views
- Toggle switches functionality
- Form validation
- File upload UI elements
"""

import re
import pytest
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:8000"


class TestPageLoad:
    """Tests for initial page load and rendering"""

    def test_page_loads_successfully(self, page: Page):
        """Page should load without errors"""
        page.goto(BASE_URL)
        expect(page).to_have_title("WheelFlow - Bicycle Wheel CFD Analysis")

    def test_header_displays_correctly(self, page: Page):
        """Header should show logo and navigation"""
        page.goto(BASE_URL)

        # Logo
        expect(page.locator(".logo h1")).to_have_text("WheelFlow")

        # Navigation buttons
        nav_buttons = page.locator(".nav-btn")
        expect(nav_buttons).to_have_count(3)
        expect(nav_buttons.nth(0)).to_have_text("Upload")
        expect(nav_buttons.nth(1)).to_have_text("Simulations")
        expect(nav_buttons.nth(2)).to_have_text("Results")

    def test_upload_view_visible_by_default(self, page: Page):
        """Upload view should be visible on page load"""
        page.goto(BASE_URL)

        upload_view = page.locator("#upload-view")
        expect(upload_view).to_be_visible()
        expect(upload_view).to_have_class(re.compile(r"active"))


class TestNavigation:
    """Tests for navigation between views"""

    def test_navigate_to_simulations(self, page: Page):
        """Clicking Simulations should show jobs view"""
        page.goto(BASE_URL)

        page.click(".nav-btn[data-view='jobs']")

        # Jobs view should be visible
        expect(page.locator("#jobs-view")).to_be_visible()
        # Upload view should be hidden
        expect(page.locator("#upload-view")).to_be_hidden()
        # Nav button should be active
        expect(page.locator(".nav-btn[data-view='jobs']")).to_have_class(re.compile(r"active"))

    def test_navigate_to_results(self, page: Page):
        """Clicking Results should show results view"""
        page.goto(BASE_URL)

        page.click(".nav-btn[data-view='results']")

        expect(page.locator("#results-view")).to_be_visible()
        expect(page.locator("#upload-view")).to_be_hidden()
        expect(page.locator(".nav-btn[data-view='results']")).to_have_class(re.compile(r"active"))

    def test_navigate_back_to_upload(self, page: Page):
        """Clicking Upload should return to upload view"""
        page.goto(BASE_URL)

        # Go to simulations first
        page.click(".nav-btn[data-view='jobs']")
        expect(page.locator("#jobs-view")).to_be_visible()

        # Navigate back to upload
        page.click(".nav-btn[data-view='upload']")
        expect(page.locator("#upload-view")).to_be_visible()
        expect(page.locator("#jobs-view")).to_be_hidden()


class TestToggleSwitches:
    """Tests for toggle switch functionality"""

    def test_toggle_switches_render_correctly(self, page: Page):
        """Toggle switches should render without text overlap"""
        page.goto(BASE_URL)

        # Check all three toggles exist
        toggles = page.locator(".toggle")
        expect(toggles).to_have_count(3)

        # Check toggle labels are visible
        expect(page.locator(".toggle-label").filter(has_text="Ground enabled")).to_be_visible()
        expect(page.locator(".toggle-label").filter(has_text="Wheel rotation enabled")).to_be_visible()
        expect(page.locator(".toggle-label").filter(has_text="GPU (RTX 3090)")).to_be_visible()

    def test_ground_toggle_is_checked_by_default(self, page: Page):
        """Ground toggle should be checked by default"""
        page.goto(BASE_URL)

        ground_toggle = page.locator("#ground-enabled")
        expect(ground_toggle).to_be_checked()

    def test_wheel_rotation_toggle_is_checked_by_default(self, page: Page):
        """Wheel rotation toggle should be checked by default"""
        page.goto(BASE_URL)

        rotation_toggle = page.locator("#rolling-enabled")
        expect(rotation_toggle).to_be_checked()

    def test_gpu_toggle_is_unchecked_by_default(self, page: Page):
        """GPU toggle should be unchecked by default"""
        page.goto(BASE_URL)

        gpu_toggle = page.locator("#gpu-acceleration")
        expect(gpu_toggle).not_to_be_checked()

    def test_toggle_can_be_clicked(self, page: Page):
        """Clicking toggle should change its state"""
        page.goto(BASE_URL)

        ground_toggle = page.locator("#ground-enabled")
        expect(ground_toggle).to_be_checked()

        # Click to uncheck
        page.locator(".toggle").filter(has_text="Ground enabled").click()
        expect(ground_toggle).not_to_be_checked()

        # Click to check again
        page.locator(".toggle").filter(has_text="Ground enabled").click()
        expect(ground_toggle).to_be_checked()

    def test_toggle_slider_has_proper_dimensions(self, page: Page):
        """Toggle slider should have proper width (44px) to prevent overlap"""
        page.goto(BASE_URL)

        slider = page.locator(".toggle-slider").first
        box = slider.bounding_box()

        # Toggle should be approximately 44px wide
        assert box is not None
        assert box["width"] >= 40, f"Toggle width {box['width']}px is too narrow"
        assert box["width"] <= 50, f"Toggle width {box['width']}px is too wide"


class TestFormValidation:
    """Tests for form validation"""

    def test_run_button_disabled_without_upload(self, page: Page):
        """Run button should be disabled when no file uploaded"""
        page.goto(BASE_URL)

        run_btn = page.locator("#run-btn")
        expect(run_btn).to_be_disabled()

    def test_validation_message_visible_when_disabled(self, page: Page):
        """Validation message should be visible when button is disabled"""
        page.goto(BASE_URL)

        validation_msg = page.locator("#validation-msg")
        expect(validation_msg).to_be_visible()
        expect(validation_msg).to_contain_text("Upload a geometry file first")

    def test_speed_hint_displays_conversion(self, page: Page):
        """Speed hint should show km/h and mph conversion"""
        page.goto(BASE_URL)

        speed_hint = page.locator("#speed-hint")
        expect(speed_hint).to_be_visible()
        expect(speed_hint).to_contain_text("km/h")
        expect(speed_hint).to_contain_text("mph")

    def test_speed_hint_updates_on_input(self, page: Page):
        """Speed hint should update when speed value changes"""
        page.goto(BASE_URL)

        speed_input = page.locator("#speed")
        speed_input.fill("20")

        speed_hint = page.locator("#speed-hint")
        # 20 m/s = 72 km/h = 44.7 mph
        expect(speed_hint).to_contain_text("72 km/h")


class TestUploadZone:
    """Tests for file upload zone"""

    def test_upload_zone_visible(self, page: Page):
        """Upload zone should be visible"""
        page.goto(BASE_URL)

        upload_zone = page.locator("#upload-zone")
        expect(upload_zone).to_be_visible()

    def test_upload_zone_has_instructions(self, page: Page):
        """Upload zone should show drag & drop instructions"""
        page.goto(BASE_URL)

        expect(page.locator(".upload-content p")).to_contain_text("Drag & drop")
        expect(page.locator(".upload-content span")).to_contain_text("click to browse")

    def test_file_info_hidden_initially(self, page: Page):
        """File info should be hidden when no file uploaded"""
        page.goto(BASE_URL)

        file_info = page.locator("#file-info")
        expect(file_info).to_have_class(re.compile(r"hidden"))


class TestEmptyStates:
    """Tests for empty state displays"""

    def test_simulations_empty_state(self, page: Page):
        """Simulations view should show empty state message"""
        page.goto(BASE_URL)
        page.click(".nav-btn[data-view='jobs']")

        empty_state = page.locator("#jobs-view .empty-state")
        expect(empty_state).to_be_visible()
        expect(empty_state).to_contain_text("No simulations yet")

    def test_results_empty_state(self, page: Page):
        """Results view should show empty state message"""
        page.goto(BASE_URL)
        page.click(".nav-btn[data-view='results']")

        empty_state = page.locator("#results-view .empty-state")
        expect(empty_state).to_be_visible()
        expect(empty_state).to_contain_text("No results to display")


class Test3DViewer:
    """Tests for 3D viewer panel"""

    def test_viewer_panel_visible(self, page: Page):
        """3D viewer panel should be visible"""
        page.goto(BASE_URL)

        viewer_panel = page.locator(".viewer-panel")
        expect(viewer_panel).to_be_visible()

    def test_viewer_has_placeholder(self, page: Page):
        """Viewer should show placeholder when no model loaded"""
        page.goto(BASE_URL)

        placeholder = page.locator(".viewer-placeholder")
        expect(placeholder).to_be_visible()
        expect(placeholder).to_contain_text("Upload a model to preview")

    def test_viewer_controls_visible(self, page: Page):
        """Viewer controls should be visible"""
        page.goto(BASE_URL)

        controls = page.locator(".viewer-controls")
        expect(controls).to_be_visible()

        # Reset and wireframe buttons
        expect(controls.locator(".btn-icon")).to_have_count(2)


class TestFormFields:
    """Tests for form field defaults and functionality"""

    def test_speed_default_value(self, page: Page):
        """Speed should default to 13.9 m/s"""
        page.goto(BASE_URL)

        speed_input = page.locator("#speed")
        expect(speed_input).to_have_value("13.9")

    def test_wheel_radius_default_value(self, page: Page):
        """Wheel radius should default to 0.325 m"""
        page.goto(BASE_URL)

        radius_input = page.locator("#wheel-radius")
        expect(radius_input).to_have_value("0.325")

    def test_yaw_angles_default_value(self, page: Page):
        """Yaw angles should default to 0, 5, 10, 15, 20"""
        page.goto(BASE_URL)

        yaw_input = page.locator("#yaw-angles")
        expect(yaw_input).to_have_value("0, 5, 10, 15, 20")

    def test_mesh_quality_default_value(self, page: Page):
        """Mesh quality should default to standard"""
        page.goto(BASE_URL)

        quality_select = page.locator("#quality")
        expect(quality_select).to_have_value("standard")

    def test_ground_type_options(self, page: Page):
        """Ground type should have Moving and Slip options"""
        page.goto(BASE_URL)

        ground_select = page.locator("#ground-type")
        options = ground_select.locator("option")

        expect(options).to_have_count(2)
        expect(options.nth(0)).to_have_text("Moving (belt)")
        expect(options.nth(1)).to_have_text("Slip")


# Pytest fixtures for Playwright
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
    }

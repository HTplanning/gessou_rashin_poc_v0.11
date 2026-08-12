import json
import os
import sys
import unittest

# Allow `python -m unittest discover -s tests -v` from the project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from app import app
except ModuleNotFoundError as exc:
    if exc.name == "flask":
        app = None
    else:
        raise

from astronomy import calculate_birth_astronomy, calculate_birth_date_astronomy
from phase_classifier import classify_phase, classify_possible_phases


class TestAstronomy(unittest.TestCase):
    def test_reference_birth_data_known_time(self) -> None:
        """Test 1: known birth time keeps the existing exact calculation."""
        result = calculate_birth_astronomy(
            birth_date="1964-09-03",
            birth_time="11:23",
            timezone_name="Asia/Tokyo",
        )

        self.assertEqual(
            result["utc_datetime"].strftime("%Y-%m-%d %H:%M:%S UTC"),
            "1964-09-03 02:23:00 UTC",
        )

        tolerance = 0.0001
        self.assertAlmostEqual(
            float(result["sun_longitude"]), 160.60945188, delta=tolerance
        )
        self.assertAlmostEqual(
            float(result["moon_longitude"]), 119.86709682, delta=tolerance
        )
        self.assertAlmostEqual(
            float(result["angle_difference"]), 319.25764494, delta=tolerance
        )

        phase = classify_phase(float(result["angle_difference"]))
        self.assertEqual(phase["id"], "P08")
        self.assertEqual(phase["name"], "欠けていく三日月")


class TestProvisionalPhaseBoundaries(unittest.TestCase):
    def test_boundaries(self) -> None:
        """Test 2: 45-degree boundaries and 360->0 normalization."""
        cases = [
            (0.0, "P01"),
            (44.9999, "P01"),
            (45.0, "P02"),
            (315.0, "P08"),
            (359.9999, "P08"),
            (360.0, "P01"),
        ]
        for angle, expected_id in cases:
            with self.subTest(angle=angle):
                self.assertEqual(classify_phase(angle)["id"], expected_id)

    def test_possible_phases_handles_wraparound(self) -> None:
        result = classify_possible_phases([359.5, 0.5])
        self.assertEqual(result["classification_status"], "ambiguous")
        self.assertEqual(
            [phase["id"] for phase in result["possible_phases"]],
            ["P08", "P01"],
        )


class TestUnknownBirthTime(unittest.TestCase):
    def test_stable_day_returns_one_candidate(self) -> None:
        """Test 3: 1964-09-04 stays within P08 for the whole JST date."""
        day = calculate_birth_date_astronomy(
            birth_date="1964-09-04",
            timezone_name="Asia/Tokyo",
            interval_minutes=30,
        )
        result = classify_possible_phases(day["angle_differences"])

        self.assertEqual(result["classification_status"], "stable")
        self.assertEqual(len(result["possible_phases"]), 1)
        self.assertEqual(result["possible_phases"][0]["id"], "P08")

    def test_ambiguous_day_returns_multiple_candidates(self) -> None:
        """Test 4: 1964-09-03 crosses the 315-degree P07/P08 boundary."""
        day = calculate_birth_date_astronomy(
            birth_date="1964-09-03",
            timezone_name="Asia/Tokyo",
            interval_minutes=30,
        )
        result = classify_possible_phases(day["angle_differences"])

        self.assertEqual(result["classification_status"], "ambiguous")
        self.assertGreaterEqual(len(result["possible_phases"]), 2)
        self.assertEqual(
            [phase["id"] for phase in result["possible_phases"]],
            ["P07", "P08"],
        )


class TestWebInputUI(unittest.TestCase):
    def setUp(self) -> None:
        self.template_path = os.path.join(PROJECT_ROOT, "templates", "index.html")
        self.js_path = os.path.join(PROJECT_ROOT, "static", "app.js")
        self.css_path = os.path.join(PROJECT_ROOT, "static", "style.css")

    def read_ui_files(self) -> tuple[str, str, str]:
        with open(self.template_path, encoding="utf-8") as handle:
            html = handle.read()
        with open(self.js_path, encoding="utf-8") as handle:
            js = handle.read()
        with open(self.css_path, encoding="utf-8") as handle:
            css = handle.read()
        return html, js, css

    def test_birthplace_placeholder_uses_kobe_example(self) -> None:
        """v0.11: birthplace input example is Kobe while calculation fixtures remain unchanged."""
        html, _js, _css = self.read_ui_files()

        self.assertIn('placeholder="例：兵庫県神戸市"', html)
        self.assertNotIn('placeholder="例：兵庫県小野市"', html)

    def test_template_uses_custom_datetime_picker_not_native_date_time(self) -> None:
        """v0.11: native date/time controls are replaced by Vue-controlled triggers."""
        html, _js, _css = self.read_ui_files()

        self.assertIn('id="app"', html)
        self.assertNotIn('type="date"', html)
        self.assertNotIn('type="time"', html)
        self.assertIn('@click="openDatePicker"', html)
        self.assertIn('@click="openTimePicker"', html)
        self.assertIn('aria-haspopup="dialog"', html)
        self.assertIn('name="birth_date" :value="form.birth_date"', html)
        self.assertIn('name="birth_time" :value="form.birth_time"', html)
        self.assertIn('v-model="form.birth_place"', html)

    def test_picker_has_confirm_cancel_and_temporary_state(self) -> None:
        """v0.11: only confirm writes temporary picker values to form state."""
        html, js, _css = self.read_ui_files()

        self.assertIn('@click="cancelPicker"', html)
        self.assertIn('@click="confirmDatePicker"', html)
        self.assertIn('@click="confirmTimePicker"', html)
        self.assertIn('originalValue: ""', js)
        self.assertIn('this.picker.originalValue = this.form.birth_date;', js)
        self.assertIn('this.picker.originalValue = this.form.birth_time;', js)
        self.assertIn('this.form.birth_date = `${this.padYear(year)}-${this.pad2(month)}-${this.pad2(day)}`;', js)
        self.assertIn('this.form.birth_time = `${this.pad2(hour)}:${this.pad2(minute)}`;', js)
        self.assertIn('// Temporary picker state is intentionally discarded. form values are untouched.', js)

    def test_empty_picker_starts_from_device_local_now_without_committing(self) -> None:
        """v0.11: empty fields use local now inside picker, not as form values."""
        _html, js, _css = self.read_ui_files()

        self.assertIn('const now = new Date();', js)
        self.assertIn('year: now.getFullYear()', js)
        self.assertIn('month: now.getMonth() + 1', js)
        self.assertIn('day: now.getDate()', js)
        self.assertIn('hour: now.getHours()', js)
        self.assertIn('minute: now.getMinutes()', js)
        self.assertIn('this.parseDateValue(this.form.birth_date) ||', js)
        self.assertIn('this.parseTimeValue(this.form.birth_time) ||', js)
        self.assertNotIn('primeCurrentValue', js)

    def test_date_picker_validates_leap_year_and_month_length(self) -> None:
        """v0.11: impossible dates are prevented before confirm."""
        html, js, _css = self.read_ui_files()

        self.assertIn('isLeapYear(year)', js)
        self.assertIn('year % 400 === 0', js)
        self.assertIn('daysInMonth(year, month)', js)
        self.assertIn('this.clampPickerDay();', js)
        self.assertIn(':disabled="!isDateSelectionValid()"', html)
        self.assertIn('西暦1〜9999年', html)

    def test_time_picker_is_24_hour_and_one_minute_resolution(self) -> None:
        """v0.11: 00:00 through 23:59 can be represented at one-minute resolution."""
        html, js, _css = self.read_ui_files()

        self.assertIn('Array.from({ length: 24 }', js)
        self.assertIn('Array.from({ length: 60 }', js)
        self.assertIn('24時間表記', html)
        self.assertIn('1分単位', html)
        self.assertIn('clearBirthTimeFromPicker', html)

    def test_scroll_touch_mouse_and_keyboard_hooks_exist(self) -> None:
        """v0.11: custom wheels support scroll/tap and keyboard arrows; Escape cancels."""
        html, js, css = self.read_ui_files()

        self.assertIn("@scroll.passive=\"onWheelScroll('month', $event)\"", html)
        self.assertIn("@scroll.passive=\"onWheelScroll('minute', $event)\"", html)
        self.assertIn('@keydown.up.prevent="nudgeWheel', html)
        self.assertIn('@keydown.down.prevent="nudgeWheel', html)
        self.assertIn('@keydown.esc.stop.prevent="cancelPicker"', html)
        self.assertIn('scroll-snap-type: y mandatory;', css)
        self.assertIn('-webkit-overflow-scrolling: touch;', css)
        self.assertIn('WHEEL_ITEM_HEIGHT = 44', js)

    def test_form_reset_logic_clears_all_three_fields_result_and_errors(self) -> None:
        """v0.11: reset explicitly empties fields and clears result/errors."""
        html, js, _css = self.read_ui_files()

        self.assertIn('class="birth-form"', html)
        self.assertIn('@reset.prevent="resetForm"', html)
        self.assertIn('this.form.birth_date = "";', js)
        self.assertIn('this.form.birth_time = "";', js)
        self.assertIn('this.form.birth_place = "";', js)
        self.assertIn('this.errors = [];', js)
        self.assertIn('this.result = null;', js)

    def test_form_controls_keep_fixed_height_and_centered_datetime_display(self) -> None:
        """v0.11: external controls preserve v0.9 height/alignment."""
        _html, _js, css = self.read_ui_files()

        self.assertIn('align-content: start;', css)
        self.assertIn('align-self: start;', css)
        self.assertIn('--form-control-height: 48px;', css)
        self.assertIn('.picker-trigger {', css)
        self.assertIn('height: var(--form-control-height);', css)
        self.assertIn('justify-content: center;', css)
        self.assertIn('text-align: center;', css)

    def test_stylesheet_and_vue_script_are_cache_busted_for_v011(self) -> None:
        """v0.11: page loads Vue code and v0.11 static assets."""
        html, _js, _css = self.read_ui_files()

        self.assertIn("filename='style.css', v='0.11'", html)
        self.assertIn("vue@3/dist/vue.global.prod.js", html)
        self.assertIn("filename='app.js', v='0.11'", html)
        self.assertIn('SHUNKA PROJECT / PoC v0.11', html)
        self.assertIn('@submit.prevent="calculate"', html)


@unittest.skipIf(app is None, "Flask is not installed in the current test environment")
class TestCalculateAPI(unittest.TestCase):
    def setUp(self) -> None:
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.js_path = os.path.join(PROJECT_ROOT, "static", "app.js")

    def post_json(self, payload: dict) -> tuple[int, dict]:
        response = self.client.post(
            "/api/calculate",
            data=json.dumps(payload),
            content_type="application/json",
        )
        return response.status_code, response.get_json()

    def test_known_birth_time_returns_exact_p08(self) -> None:
        status, payload = self.post_json(
            {
                "birth_date": "1964-09-03",
                "birth_time": "11:23",
                "birth_place": "兵庫県小野市",
            }
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        result = payload["result"]
        self.assertTrue(result["birth_time_known"])
        self.assertEqual(result["classification_status"], "exact")
        self.assertEqual(result["phase_id"], "P08")
        self.assertEqual(result["phase_name"], "欠けていく三日月")
        self.assertAlmostEqual(result["angle_difference"], 319.25764494, delta=0.0001)
        self.assertEqual(result["logic_version"], "PoC標準月相8分類（45°区分）")

    def test_unknown_birth_time_stable(self) -> None:
        status, payload = self.post_json(
            {
                "birth_date": "1964-09-04",
                "birth_time": "",
                "birth_place": "兵庫県小野市",
            }
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        result = payload["result"]
        self.assertFalse(result["birth_time_known"])
        self.assertEqual(result["classification_status"], "stable")
        self.assertEqual([p["id"] for p in result["possible_phases"]], ["P08"])

    def test_unknown_birth_time_ambiguous(self) -> None:
        status, payload = self.post_json(
            {
                "birth_date": "1964-09-03",
                "birth_time": "",
                "birth_place": "兵庫県小野市",
            }
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        result = payload["result"]
        self.assertFalse(result["birth_time_known"])
        self.assertEqual(result["classification_status"], "ambiguous")
        self.assertEqual(
            [p["id"] for p in result["possible_phases"]],
            ["P07", "P08"],
        )

    def test_validation_errors_are_returned_as_json(self) -> None:
        status, payload = self.post_json(
            {"birth_date": "", "birth_time": "", "birth_place": ""}
        )

        self.assertEqual(status, 400)
        self.assertFalse(payload["success"])
        self.assertEqual(
            payload["errors"],
            ["生年月日を入力してください。", "出生地を入力してください。"],
        )

    def test_root_serves_vue_screen(self) -> None:
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("SHUNKA PROJECT / PoC v0.11", html)
        self.assertIn("/static/app.js?v=0.11", html)
        with open(self.js_path, encoding="utf-8") as handle:
            js = handle.read()
        self.assertIn("/api/calculate", js)


if __name__ == "__main__":
    unittest.main()

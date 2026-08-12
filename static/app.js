/* 月相羅針 計算PoC v0.11｜全端末共通 生年月日・出生時間入力UI版
 *
 * Vue.js is responsible only for input state, custom date/time picker UI,
 * API communication, errors, loading state, and rendering. Astronomical
 * calculation and phase classification remain in Flask / Python.
 */

(() => {
  "use strict";

  if (typeof Vue === "undefined") {
    console.error("Vue 3 could not be loaded.");
    return;
  }

  const { createApp } = Vue;
  const WHEEL_ITEM_HEIGHT = 44;

  createApp({
    data() {
      return {
        form: {
          birth_date: "",
          birth_time: "",
          birth_place: "",
        },
        errors: [],
        loading: false,
        result: null,
        picker: {
          type: null,
          originalValue: "",
          date: {
            yearText: "",
            month: 1,
            day: 1,
          },
          time: {
            hour: 0,
            minute: 0,
          },
        },
        scrollTimers: {},
      };
    },

    computed: {
      months() {
        return Array.from({ length: 12 }, (_item, index) => index + 1);
      },

      days() {
        const year = this.pickerYear();
        const month = Number(this.picker.date.month);
        const count = this.daysInMonth(year, month);
        return Array.from({ length: count }, (_item, index) => index + 1);
      },

      hours() {
        return Array.from({ length: 24 }, (_item, index) => index);
      },

      minutes() {
        return Array.from({ length: 60 }, (_item, index) => index);
      },
    },

    methods: {
      pad2(value) {
        return String(value).padStart(2, "0");
      },

      padYear(value) {
        return String(value).padStart(4, "0");
      },

      currentLocalParts() {
        const now = new Date();
        return {
          year: now.getFullYear(),
          month: now.getMonth() + 1,
          day: now.getDate(),
          hour: now.getHours(),
          minute: now.getMinutes(),
        };
      },

      currentLocalDate() {
        const now = this.currentLocalParts();
        return `${this.padYear(now.year)}-${this.pad2(now.month)}-${this.pad2(now.day)}`;
      },

      currentLocalTime() {
        const now = this.currentLocalParts();
        return `${this.pad2(now.hour)}:${this.pad2(now.minute)}`;
      },

      parseDateValue(value) {
        const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
        if (!match) return null;
        const year = Number(match[1]);
        const month = Number(match[2]);
        const day = Number(match[3]);
        return this.isValidDateParts(year, month, day) ? { year, month, day } : null;
      },

      parseTimeValue(value) {
        const match = /^(\d{2}):(\d{2})$/.exec(value || "");
        if (!match) return null;
        const hour = Number(match[1]);
        const minute = Number(match[2]);
        if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
        return { hour, minute };
      },

      pickerYear() {
        const year = Number(this.picker.date.yearText);
        return Number.isInteger(year) ? year : 0;
      },

      isLeapYear(year) {
        return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
      },

      daysInMonth(year, month) {
        if (!Number.isInteger(year) || year < 1 || year > 9999) return 31;
        if (month === 2) return this.isLeapYear(year) ? 29 : 28;
        if ([4, 6, 9, 11].includes(month)) return 30;
        return 31;
      },

      isValidDateParts(year, month, day) {
        if (!Number.isInteger(year) || year < 1 || year > 9999) return false;
        if (!Number.isInteger(month) || month < 1 || month > 12) return false;
        if (!Number.isInteger(day) || day < 1) return false;
        return day <= this.daysInMonth(year, month);
      },

      isDateSelectionValid() {
        return this.isValidDateParts(
          this.pickerYear(),
          Number(this.picker.date.month),
          Number(this.picker.date.day),
        );
      },

      clampPickerDay() {
        const year = this.pickerYear();
        const month = Number(this.picker.date.month);
        if (year < 1 || year > 9999 || month < 1 || month > 12) return;
        const maxDay = this.daysInMonth(year, month);
        if (this.picker.date.day > maxDay) {
          this.picker.date.day = maxDay;
        }
      },

      formatBirthDateDisplay(value) {
        const parsed = this.parseDateValue(value);
        if (!parsed) return "生年月日を選択";
        return `${this.padYear(parsed.year)}年 ${this.pad2(parsed.month)}月 ${this.pad2(parsed.day)}日`;
      },

      formatBirthTimeDisplay(value) {
        const parsed = this.parseTimeValue(value);
        if (!parsed) return "出生時間を選択";
        return `${this.pad2(parsed.hour)}時 ${this.pad2(parsed.minute)}分`;
      },

      openDatePicker() {
        const current = this.currentLocalParts();
        const initial = this.parseDateValue(this.form.birth_date) || {
          year: current.year,
          month: current.month,
          day: current.day,
        };

        this.picker.type = "date";
        this.picker.originalValue = this.form.birth_date;
        this.picker.date.yearText = String(initial.year);
        this.picker.date.month = initial.month;
        this.picker.date.day = initial.day;
        this.clampPickerDay();
        document.body.classList.add("modal-open");

        this.$nextTick(() => {
          this.syncDateWheels();
          if (this.$refs.dateDialog) this.$refs.dateDialog.focus();
        });
      },

      openTimePicker() {
        const current = this.currentLocalParts();
        const initial = this.parseTimeValue(this.form.birth_time) || {
          hour: current.hour,
          minute: current.minute,
        };

        this.picker.type = "time";
        this.picker.originalValue = this.form.birth_time;
        this.picker.time.hour = initial.hour;
        this.picker.time.minute = initial.minute;
        document.body.classList.add("modal-open");

        this.$nextTick(() => {
          this.syncTimeWheels();
          if (this.$refs.timeDialog) this.$refs.timeDialog.focus();
        });
      },

      closePicker(returnFocus = true) {
        const previousType = this.picker.type;
        this.picker.type = null;
        document.body.classList.remove("modal-open");

        if (returnFocus) {
          this.$nextTick(() => {
            const target = previousType === "date" ? this.$refs.dateTrigger : this.$refs.timeTrigger;
            if (target && typeof target.focus === "function") target.focus();
          });
        }
      },

      cancelPicker() {
        // Temporary picker state is intentionally discarded. form values are untouched.
        this.closePicker(true);
      },

      confirmDatePicker() {
        if (!this.isDateSelectionValid()) return;
        const year = this.pickerYear();
        const month = Number(this.picker.date.month);
        const day = Number(this.picker.date.day);
        this.form.birth_date = `${this.padYear(year)}-${this.pad2(month)}-${this.pad2(day)}`;
        this.closePicker(true);
      },

      confirmTimePicker() {
        const hour = Number(this.picker.time.hour);
        const minute = Number(this.picker.time.minute);
        this.form.birth_time = `${this.pad2(hour)}:${this.pad2(minute)}`;
        this.closePicker(true);
      },

      clearBirthTimeFromPicker() {
        this.form.birth_time = "";
        this.closePicker(true);
      },

      onYearInput(event) {
        const digits = String(event.target.value || "").replace(/\D/g, "").slice(0, 4);
        this.picker.date.yearText = digits;
        event.target.value = digits;
        this.clampPickerDay();
        this.$nextTick(() => this.syncDayWheel());
      },

      normalizeYear() {
        let year = this.pickerYear();
        if (!Number.isInteger(year) || year < 1) year = 1;
        if (year > 9999) year = 9999;
        this.picker.date.yearText = String(year);
        this.clampPickerDay();
        this.$nextTick(() => this.syncDayWheel());
      },

      adjustYear(delta) {
        let year = this.pickerYear();
        if (!Number.isInteger(year) || year < 1 || year > 9999) {
          year = this.currentLocalParts().year;
        }
        year = Math.min(9999, Math.max(1, year + delta));
        this.picker.date.yearText = String(year);
        this.clampPickerDay();
        this.$nextTick(() => this.syncDayWheel());
      },

      stepYearFromWheel(event) {
        if (event.deltaY === 0) return;
        this.adjustYear(event.deltaY > 0 ? -1 : 1);
      },

      selectMonth(month) {
        this.picker.date.month = month;
        this.clampPickerDay();
        this.$nextTick(() => {
          this.scrollColumnToValue("monthWheel", this.months, month, "smooth");
          this.syncDayWheel();
        });
      },

      selectDay(day) {
        this.picker.date.day = day;
        this.scrollColumnToValue("dayWheel", this.days, day, "smooth");
      },

      selectHour(hour) {
        this.picker.time.hour = hour;
        this.scrollColumnToValue("hourWheel", this.hours, hour, "smooth");
      },

      selectMinute(minute) {
        this.picker.time.minute = minute;
        this.scrollColumnToValue("minuteWheel", this.minutes, minute, "smooth");
      },

      pickerValues(kind) {
        if (kind === "month") return this.months;
        if (kind === "day") return this.days;
        if (kind === "hour") return this.hours;
        if (kind === "minute") return this.minutes;
        return [];
      },

      pickerCurrentValue(kind) {
        if (kind === "month") return this.picker.date.month;
        if (kind === "day") return this.picker.date.day;
        if (kind === "hour") return this.picker.time.hour;
        if (kind === "minute") return this.picker.time.minute;
        return null;
      },

      setPickerValue(kind, value) {
        if (kind === "month") {
          this.picker.date.month = value;
          this.clampPickerDay();
          this.$nextTick(() => this.syncDayWheel());
        } else if (kind === "day") {
          this.picker.date.day = value;
        } else if (kind === "hour") {
          this.picker.time.hour = value;
        } else if (kind === "minute") {
          this.picker.time.minute = value;
        }
      },

      onWheelScroll(kind, event) {
        const element = event.currentTarget;
        window.clearTimeout(this.scrollTimers[kind]);
        this.scrollTimers[kind] = window.setTimeout(() => {
          const values = this.pickerValues(kind);
          if (!values.length) return;
          const index = Math.min(
            values.length - 1,
            Math.max(0, Math.round(element.scrollTop / WHEEL_ITEM_HEIGHT)),
          );
          this.setPickerValue(kind, values[index]);
          element.scrollTo({ top: index * WHEEL_ITEM_HEIGHT, behavior: "smooth" });
        }, 90);
      },

      nudgeWheel(kind, delta) {
        const values = this.pickerValues(kind);
        const current = this.pickerCurrentValue(kind);
        const index = Math.max(0, values.indexOf(current));
        const nextIndex = Math.min(values.length - 1, Math.max(0, index + delta));
        const nextValue = values[nextIndex];
        this.setPickerValue(kind, nextValue);
        const refName = `${kind}Wheel`;
        this.$nextTick(() => this.scrollColumnToValue(refName, this.pickerValues(kind), nextValue, "smooth"));
      },

      scrollColumnToValue(refName, values, value, behavior = "auto") {
        const element = this.$refs[refName];
        if (!element) return;
        const index = values.indexOf(value);
        if (index < 0) return;
        element.scrollTo({ top: index * WHEEL_ITEM_HEIGHT, behavior });
      },

      syncDateWheels() {
        this.scrollColumnToValue("monthWheel", this.months, this.picker.date.month);
        this.scrollColumnToValue("dayWheel", this.days, this.picker.date.day);
      },

      syncDayWheel() {
        this.scrollColumnToValue("dayWheel", this.days, this.picker.date.day);
      },

      syncTimeWheels() {
        this.scrollColumnToValue("hourWheel", this.hours, this.picker.time.hour);
        this.scrollColumnToValue("minuteWheel", this.minutes, this.picker.time.minute);
      },

      resetForm() {
        // v0.5以降の仕様を維持：前回計算値へ戻さず、3項目とも空欄にする。
        this.form.birth_date = "";
        this.form.birth_time = "";
        this.form.birth_place = "";
        this.errors = [];
        this.result = null;
        if (this.picker.type) this.closePicker(false);
      },

      async calculate() {
        if (this.loading) return;

        this.loading = true;
        this.errors = [];
        this.result = null;

        try {
          const response = await fetch("/api/calculate", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            body: JSON.stringify({
              birth_date: this.form.birth_date,
              birth_time: this.form.birth_time,
              birth_place: this.form.birth_place,
            }),
          });

          let payload;
          try {
            payload = await response.json();
          } catch (_error) {
            payload = null;
          }

          if (!payload || payload.success !== true) {
            this.errors = payload && Array.isArray(payload.errors)
              ? payload.errors
              : ["計算中にエラーが発生しました。もう一度お試しください。"];
            return;
          }

          this.result = payload.result;
        } catch (_error) {
          this.errors = ["サーバーとの通信に失敗しました。もう一度お試しください。"];
        } finally {
          this.loading = false;
        }
      },

      formatNumber(value) {
        const number = Number(value);
        return Number.isFinite(number) ? number.toFixed(8) : "";
      },

      candidateLabel(index) {
        if (!this.result || !Array.isArray(this.result.possible_phases)) {
          return "候補";
        }
        return this.result.possible_phases.length > 1 ? `候補${index + 1}` : "候補";
      },

      coordinatesText(result) {
        if (!result) return "";
        const latitude = result.latitude;
        const longitude = result.longitude;
        if (typeof latitude === "number" && typeof longitude === "number") {
          return `${latitude}, ${longitude}`;
        }
        return "PoCでは未設定";
      },

      statusLabel(status) {
        if (status === "stable") return "stable（一日を通して同一分類）";
        if (status === "ambiguous") return "ambiguous（複数候補あり）";
        if (status === "exact") return "exact（出生時間あり）";
        return status || "";
      },
    },
  }).mount("#app");
})();

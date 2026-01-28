/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AttendanceSummaryWidget extends Component {
    static template = "attendance_timeoff_automation.AttendanceSummaryWidget";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            summaryData: [],
            dateFrom: this.getFirstDayOfMonth(),
            dateTo: this.getCurrentDate(),
            loading: false,
        });

        onWillStart(async () => {
            await this.loadSummaryData();
        });
    }

    getFirstDayOfMonth() {
        const today = new Date();
        return new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
    }

    getCurrentDate() {
        return new Date().toISOString().split('T')[0];
    }

    async loadSummaryData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "hr.attendance.summary",
                "get_summary_data",
                [],
                {
                    date_from: this.state.dateFrom,
                    date_to: this.state.dateTo,
                }
            );
            this.state.summaryData = data;
        } catch (error) {
            console.error("Error loading attendance summary:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async onDateChange() {
        await this.loadSummaryData();
    }

    getProgressBarClass(percentage) {
        if (percentage >= 90) return "bg-success";
        if (percentage >= 70) return "bg-warning";
        return "bg-danger";
    }

    getStatusBadgeClass(percentage) {
        if (percentage >= 90) return "badge-success";
        if (percentage >= 70) return "badge-warning";
        return "badge-danger";
    }
}

registry.category("view_widgets").add("attendance_summary_widget", AttendanceSummaryWidget);

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CrmLeadActivityDashboard extends Component {
    static template = "crm_lead_activity_report.CrmLeadActivityDashboard";
    static props = {
        "*": true, // Accept any props for client action compatibility
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: false,
            dateFrom: this.getFirstDayOfMonth(),
            dateTo: this.getCurrentDate(),
            teamId: false,
            userId: false,
            includeArchived: false,
            data: {
                kpis: { total: 0, worked: 0, untouched: 0, contacted: 0, moved_to_briefed: 0, call_back: 0, proposal_to_send: 0, lost: 0, internal_notes: 0, uncontacted: 0 },
                analytics: { contact_rate: 0, loss_rate: 0, avg_days_to_contact: 0, avg_internal_notes_per_contacted: 0, top_lost_reason: "N/A", positive_notes: 0, negative_notes: 0, neutral_notes: 0 },
                stages: [],
                lost_reasons: [],
                reason_rows: [],
                by_salesperson: [],
                lines: [],
                teams: [],
                users: [],
                briefed_by_salesperson: [],
                lost_by_salesperson: [],
                observations: [],
            },
        });

        onWillStart(async () => {
            await this.refresh();
        });
    }

    getFirstDayOfMonth() {
        const today = new Date();
        return new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split("T")[0];
    }

    getCurrentDate() {
        return new Date().toISOString().split("T")[0];
    }

    async refresh() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "crm.lead.activity.report.wizard",
                "get_dashboard_data",
                [],
                {
                    date_from: this.state.dateFrom,
                    date_to: this.state.dateTo,
                    team_id: this.state.teamId || false,
                    user_id: this.state.userId || false,
                    include_archived: this.state.includeArchived,
                }
            );
            this.state.data = data;
        } catch (error) {
            console.error("Error loading CRM lead activity dashboard:", error);
        } finally {
            this.state.loading = false;
        }
    }

    onTeamChange(ev) {
        this.state.teamId = ev.target.value ? parseInt(ev.target.value, 10) : false;
    }

    onUserChange(ev) {
        this.state.userId = ev.target.value ? parseInt(ev.target.value, 10) : false;
    }

    onArchivedToggle(ev) {
        this.state.includeArchived = !!ev.target.checked;
    }
}

// Duplicate-safe registration avoids hard failures when assets are reloaded.
function safeRegistryAdd(category, key, value) {
    try {
        registry.category(category).add(key, value);
    } catch (_e) {
        // Ignore duplicate-key errors during asset reloads.
    }
}

// Register as both widget and client action.
safeRegistryAdd("view_widgets", "crm_lead_activity_dashboard_widget", CrmLeadActivityDashboard);
safeRegistryAdd("actions", "crm_lead_activity_dashboard_action", CrmLeadActivityDashboard);
safeRegistryAdd("actions", "crm_lead_activity_dashboard_custom_action", CrmLeadActivityDashboard);
safeRegistryAdd("actions", "crm_lead_activity_report.crm_lead_activity_dashboard_action", CrmLeadActivityDashboard);

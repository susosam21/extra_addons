/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CrmLeadActivityDashboard extends Component {
    static template = "crm_lead_activity_report.CrmLeadActivityDashboard";
    static props = { "*": true };

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
                kpis: { total: 0, contacted: 0, lost: 0, internal_notes: 0 },
                stages: [],
                lost_reasons: [],
                by_salesperson: [],
                lines: [],
                teams: [],
                users: [],
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

const actionRegistry = registry.category("actions");

// Register both canonical and namespaced tags to avoid client action lookup mismatches.
try {
    actionRegistry.add("crm_lead_activity_dashboard_action", CrmLeadActivityDashboard);
} catch (_e) {
    // Ignore duplicate-key registration errors.
}

try {
    actionRegistry.add("crm_lead_activity_report.crm_lead_activity_dashboard_action", CrmLeadActivityDashboard);
} catch (_e) {
    // Ignore duplicate-key registration errors.
}

import { defineAsyncComponent } from "vue";
import ChunkFallback from "../components/ChunkFallback.vue";

function lazyView(loader) {
  return defineAsyncComponent({
    loader,
    loadingComponent: ChunkFallback,
    delay: 80,
    timeout: 60000
  });
}

export const DashboardView = lazyView(() => import("../views/DashboardView.vue"));
export const ConversionsView = lazyView(() => import("../views/ConversionsView.vue"));
export const AccountingView = lazyView(() => import("../views/AccountingView.vue"));
export const StepsView = lazyView(() => import("../views/StepsView.vue"));
export const ChainView = lazyView(() => import("../views/ChainView.vue"));
export const AutomationsView = lazyView(() => import("../views/AutomationsView.vue"));
export const UsersView = lazyView(() => import("../views/UsersView.vue"));
export const EventsView = lazyView(() => import("../views/EventsView.vue"));
export const SettingsView = lazyView(() => import("../views/SettingsView.vue"));
export const AdminsView = lazyView(() => import("../views/AdminsView.vue"));
export const LeadsView = lazyView(() => import("../views/LeadsView.vue"));

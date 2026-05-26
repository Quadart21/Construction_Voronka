import { createRouter, createWebHistory } from "vue-router";
import AdminPanel from "../AdminPanel.vue";
import PublicLanding from "../views/PublicLanding.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: PublicLanding },
    { path: "/admin", name: "admin", component: AdminPanel }
  ]
});

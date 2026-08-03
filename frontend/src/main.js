import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import "./index.css";

const app = createApp(App);

app.config.errorHandler = (err, vm, info) => {
  console.error(`[Growth Portal] ${info}:`, err);
};

app.use(router);
app.mount("#app");

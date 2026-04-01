import React from "react";
import ReactDOM from "react-dom/client";
import { FluentProvider } from "@fluentui/react-components";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ThemeWrapper } from "./ThemeWrapper";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeWrapper>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ThemeWrapper>
  </React.StrictMode>,
);

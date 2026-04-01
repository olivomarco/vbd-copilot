import {
  createLightTheme,
  createDarkTheme,
  type BrandVariants,
} from "@fluentui/react-components";

const csaBrand: BrandVariants = {
  10: "#021526",
  20: "#042b4d",
  30: "#053d6e",
  40: "#064f8f",
  50: "#0862b1",
  60: "#0a74d2",
  70: "#0c87f3",
  80: "#3a9df5",
  90: "#68b3f7",
  100: "#96c9f9",
  110: "#b4d7fb",
  120: "#c8e2fc",
  130: "#dcedfd",
  140: "#eef6fe",
  150: "#f7fbff",
  160: "#ffffff",
};

export const lightTheme = createLightTheme(csaBrand);
export const darkTheme = createDarkTheme(csaBrand);

// Override specific tokens
lightTheme.fontFamilyBase =
  '"DM Sans", "Segoe UI Variable", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif';
lightTheme.fontFamilyMonospace =
  '"Cascadia Code", "Fira Code", "JetBrains Mono", monospace';
darkTheme.fontFamilyBase = lightTheme.fontFamilyBase;
darkTheme.fontFamilyMonospace = lightTheme.fontFamilyMonospace;

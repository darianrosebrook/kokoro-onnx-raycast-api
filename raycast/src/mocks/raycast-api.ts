import { vi } from "vitest";

export const showToast = vi.fn();

export const Toast = {
  Style: {
    Animated: "animated",
    Failure: "failure",
    Success: "success",
  },
};

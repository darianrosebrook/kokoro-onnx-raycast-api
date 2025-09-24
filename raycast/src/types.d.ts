/// <reference types="@raycast/api" />

// Type overrides to fix Raycast + React compatibility issues
declare module "react" {
  interface ReactElement {
    children?: React.ReactNode;
  }
}

// Global type declarations for Raycast environment
declare global {
  namespace JSX {
    interface Element
      extends React.ReactElement<unknown, string | React.JSXElementConstructor<unknown>> {}
  }
}

export {};

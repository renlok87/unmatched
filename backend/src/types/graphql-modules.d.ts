declare module 'graphql-validation-complexity' {
  export function createComplexityLimitRule(options: any): any;
}

declare module 'graphql-depth-limit' {
  function depthLimit(maxDepth: number, options?: any): any;
  export default depthLimit;
}

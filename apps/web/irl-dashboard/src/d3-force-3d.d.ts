// d3-force-3d has no upstream type declarations. This minimal shim lets
// TypeScript compile (and `next build` pass) while ForceGraph passes the
// untyped value through to react-force-graph-3d.
declare module "d3-force-3d";
// Node resolve hook: map the bare import "three" to the vendored copy (same as the browser importmap).
export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'three') {
    return { url: new URL('../vendor/three.module.min.js', import.meta.url).href, shortCircuit: true };
  }
  return nextResolve(specifier, context);
}

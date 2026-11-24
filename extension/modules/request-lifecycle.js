export function createRequestLifecycle(makeId = () => crypto.randomUUID()) {
  let active = null;
  let controller = null;

  function invalidate() {
    active = null;
    controller?.abort();
    controller = null;
  }

  function isCurrent(request) {
    return active !== null && active === request;
  }

  return {
    begin() {
      invalidate();
      controller = new AbortController();
      active = { id: makeId(), signal: controller.signal };
      return active;
    },
    invalidate,
    isCurrent,
    accepts(request, responseId) {
      return isCurrent(request) && responseId === request.id;
    },
    finish(request) {
      if (isCurrent(request)) {
        active = null;
        controller = null;
      }
    },
  };
}

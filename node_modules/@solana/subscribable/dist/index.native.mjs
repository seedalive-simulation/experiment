import { getAbortablePromise } from '@solana/promises';
import { SolanaError, SOLANA_ERROR__INVARIANT_VIOLATION__SUBSCRIPTION_ITERATOR_STATE_MISSING, SOLANA_ERROR__INVARIANT_VIOLATION__SUBSCRIPTION_ITERATOR_MUST_NOT_POLL_BEFORE_RESOLVING_EXISTING_MESSAGE_PROMISE, SOLANA_ERROR__SUBSCRIBABLE__RETRY_NOT_SUPPORTED } from '@solana/errors';

// ../event-target-impl/dist/index.browser.mjs
var o = globalThis.AbortController;
var t = globalThis.EventTarget;
var IDLE_STATE = Object.freeze({
  data: void 0,
  error: void 0,
  status: "idle"
});
function createReactiveActionStore(fn) {
  let state = IDLE_STATE;
  let currentController;
  const listeners = /* @__PURE__ */ new Set();
  function setState(next) {
    if (state.status === next.status && state.data === next.data && state.error === next.error) {
      return;
    }
    state = next;
    listeners.forEach((listener) => listener());
  }
  const dispatchAsync = async (...args) => {
    currentController?.abort();
    const controller = new o();
    currentController = controller;
    const { signal } = controller;
    const previousData = state.data;
    setState({ data: previousData, error: void 0, status: "running" });
    try {
      const result = await getAbortablePromise(fn(signal, ...args), signal);
      if (signal.aborted) {
        throw signal.reason;
      }
      setState({ data: result, error: void 0, status: "success" });
      return result;
    } catch (error) {
      if (signal.aborted) {
        throw signal.reason;
      }
      setState({ data: previousData, error, status: "error" });
      throw error;
    }
  };
  const dispatch = (...args) => {
    dispatchAsync(...args).catch(() => {
    });
  };
  return {
    dispatch,
    dispatchAsync,
    getState: () => state,
    reset: () => {
      currentController?.abort();
      currentController = void 0;
      setState(IDLE_STATE);
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    }
  };
}
var EXPLICIT_ABORT_TOKEN;
function createExplicitAbortToken() {
  return Symbol(
    process.env.NODE_ENV !== "production" ? "This symbol is thrown from a socket's iterator when the connection is explicitly aborted by the user" : void 0
  );
}
var UNINITIALIZED = Symbol();
function createAsyncIterableFromDataPublisher({
  abortSignal,
  dataChannelName,
  dataPublisher,
  errorChannelName
}) {
  const iteratorState = /* @__PURE__ */ new Map();
  function publishErrorToAllIterators(reason) {
    for (const [iteratorKey, state] of iteratorState.entries()) {
      if (state.__hasPolled) {
        iteratorState.delete(iteratorKey);
        state.onError(reason);
      } else {
        state.publishQueue.push({
          __type: 1 /* ERROR */,
          err: reason
        });
      }
    }
  }
  const abortController = new o();
  abortSignal.addEventListener("abort", () => {
    abortController.abort();
    publishErrorToAllIterators(EXPLICIT_ABORT_TOKEN ||= createExplicitAbortToken());
  });
  const options = { signal: abortController.signal };
  let firstError = UNINITIALIZED;
  dataPublisher.on(
    errorChannelName,
    (err) => {
      if (firstError === UNINITIALIZED) {
        firstError = err;
        abortController.abort();
        publishErrorToAllIterators(err);
      }
    },
    options
  );
  dataPublisher.on(
    dataChannelName,
    (data) => {
      iteratorState.forEach((state, iteratorKey) => {
        if (state.__hasPolled) {
          const { onData } = state;
          iteratorState.set(iteratorKey, { __hasPolled: false, publishQueue: [] });
          onData(data);
        } else {
          state.publishQueue.push({
            __type: 0 /* DATA */,
            data
          });
        }
      });
    },
    options
  );
  return {
    async *[Symbol.asyncIterator]() {
      if (abortSignal.aborted) {
        return;
      }
      if (firstError !== UNINITIALIZED) {
        throw firstError;
      }
      const iteratorKey = Symbol();
      iteratorState.set(iteratorKey, { __hasPolled: false, publishQueue: [] });
      try {
        while (true) {
          const state = iteratorState.get(iteratorKey);
          if (!state) {
            throw new SolanaError(SOLANA_ERROR__INVARIANT_VIOLATION__SUBSCRIPTION_ITERATOR_STATE_MISSING);
          }
          if (state.__hasPolled) {
            throw new SolanaError(
              SOLANA_ERROR__INVARIANT_VIOLATION__SUBSCRIPTION_ITERATOR_MUST_NOT_POLL_BEFORE_RESOLVING_EXISTING_MESSAGE_PROMISE
            );
          }
          const publishQueue = state.publishQueue;
          try {
            if (publishQueue.length) {
              state.publishQueue = [];
              for (const item of publishQueue) {
                if (item.__type === 0 /* DATA */) {
                  yield item.data;
                } else {
                  throw item.err;
                }
              }
            } else {
              yield await new Promise((resolve, reject) => {
                iteratorState.set(iteratorKey, {
                  __hasPolled: true,
                  onData: resolve,
                  onError: reject
                });
              });
            }
          } catch (e) {
            if (e === (EXPLICIT_ABORT_TOKEN ||= createExplicitAbortToken())) {
              return;
            } else {
              throw e;
            }
          }
        }
      } finally {
        iteratorState.delete(iteratorKey);
      }
    }
  };
}

// src/data-publisher.ts
function getDataPublisherFromEventEmitter(eventEmitter) {
  return {
    on(channelName, subscriber, options) {
      function innerListener(ev) {
        if (ev instanceof CustomEvent) {
          const data = ev.detail;
          subscriber(data);
        } else {
          subscriber();
        }
      }
      eventEmitter.addEventListener(channelName, innerListener, options);
      return () => {
        eventEmitter.removeEventListener(channelName, innerListener);
      };
    }
  };
}

// src/demultiplex.ts
function demultiplexDataPublisher(publisher, sourceChannelName, messageTransformer) {
  let innerPublisherState;
  const eventTarget = new t();
  const demultiplexedDataPublisher = getDataPublisherFromEventEmitter(eventTarget);
  return {
    ...demultiplexedDataPublisher,
    on(channelName, subscriber, options) {
      if (!innerPublisherState) {
        const innerPublisherUnsubscribe = publisher.on(sourceChannelName, (sourceMessage) => {
          const transformResult = messageTransformer(sourceMessage);
          if (!transformResult) {
            return;
          }
          const [destinationChannelName, message] = transformResult;
          eventTarget.dispatchEvent(
            new CustomEvent(destinationChannelName, {
              detail: message
            })
          );
        });
        innerPublisherState = {
          dispose: innerPublisherUnsubscribe,
          numSubscribers: 0
        };
      }
      innerPublisherState.numSubscribers++;
      const unsubscribe = demultiplexedDataPublisher.on(channelName, subscriber, options);
      let isActive = true;
      function handleUnsubscribe() {
        if (!isActive) {
          return;
        }
        isActive = false;
        options?.signal.removeEventListener("abort", handleUnsubscribe);
        innerPublisherState.numSubscribers--;
        if (innerPublisherState.numSubscribers === 0) {
          innerPublisherState.dispose();
          innerPublisherState = void 0;
        }
        unsubscribe();
      }
      options?.signal.addEventListener("abort", handleUnsubscribe);
      return handleUnsubscribe;
    }
  };
}
var LOADING_STATE = Object.freeze({
  data: void 0,
  error: void 0,
  status: "loading"
});
function createReactiveStoreFromDataPublisher({
  abortSignal,
  dataChannelName,
  dataPublisher,
  errorChannelName
}) {
  let currentState = LOADING_STATE;
  const subscribers = /* @__PURE__ */ new Set();
  const abortController = new o();
  abortSignal.addEventListener("abort", () => abortController.abort(abortSignal.reason));
  function notify() {
    subscribers.forEach((cb) => cb());
  }
  dataPublisher.on(
    dataChannelName,
    (data) => {
      currentState = { data, error: void 0, status: "loaded" };
      notify();
    },
    { signal: abortController.signal }
  );
  dataPublisher.on(
    errorChannelName,
    (err) => {
      if (currentState.status === "error") return;
      currentState = { data: currentState.data, error: err, status: "error" };
      abortController.abort(err);
      notify();
    },
    { signal: abortController.signal }
  );
  return {
    getError() {
      return currentState.error;
    },
    getState() {
      return currentState.data;
    },
    getUnifiedState() {
      return currentState;
    },
    retry() {
      throw new SolanaError(SOLANA_ERROR__SUBSCRIBABLE__RETRY_NOT_SUPPORTED);
    },
    subscribe(callback) {
      subscribers.add(callback);
      return () => {
        subscribers.delete(callback);
      };
    }
  };
}
function createReactiveStoreFromDataPublisherFactory({
  abortSignal,
  createDataPublisher,
  dataChannelName,
  errorChannelName
}) {
  let currentState = LOADING_STATE;
  const subscribers = /* @__PURE__ */ new Set();
  const outerController = new o();
  abortSignal.addEventListener("abort", () => outerController.abort(abortSignal.reason));
  function notify() {
    subscribers.forEach((cb) => cb());
  }
  function connect() {
    if (outerController.signal.aborted) return;
    const innerController = new o();
    const forwardAbort = () => innerController.abort(outerController.signal.reason);
    outerController.signal.addEventListener("abort", forwardAbort, { signal: innerController.signal });
    createDataPublisher().then(
      (publisher) => {
        if (innerController.signal.aborted) return;
        publisher.on(
          dataChannelName,
          (data) => {
            currentState = { data, error: void 0, status: "loaded" };
            notify();
          },
          { signal: innerController.signal }
        );
        publisher.on(
          errorChannelName,
          (err) => {
            if (currentState.status === "error") return;
            currentState = { data: currentState.data, error: err, status: "error" };
            innerController.abort(err);
            notify();
          },
          { signal: innerController.signal }
        );
      },
      (err) => {
        if (innerController.signal.aborted) return;
        currentState = { data: currentState.data, error: err, status: "error" };
        innerController.abort(err);
        notify();
      }
    );
  }
  connect();
  return {
    getError() {
      return currentState.error;
    },
    getState() {
      return currentState.data;
    },
    getUnifiedState() {
      return currentState;
    },
    retry() {
      if (outerController.signal.aborted) return;
      if (currentState.status !== "error") return;
      currentState = { data: currentState.data, error: void 0, status: "retrying" };
      notify();
      connect();
    },
    subscribe(callback) {
      subscribers.add(callback);
      return () => {
        subscribers.delete(callback);
      };
    }
  };
}

export { createAsyncIterableFromDataPublisher, createReactiveActionStore, createReactiveStoreFromDataPublisher, createReactiveStoreFromDataPublisherFactory, demultiplexDataPublisher, getDataPublisherFromEventEmitter };
//# sourceMappingURL=index.native.mjs.map
//# sourceMappingURL=index.native.mjs.map
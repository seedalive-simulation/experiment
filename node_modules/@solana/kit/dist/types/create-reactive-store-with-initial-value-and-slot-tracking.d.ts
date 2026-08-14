import type { PendingRpcRequest } from '@solana/rpc';
import type { PendingRpcSubscriptionsRequest } from '@solana/rpc-subscriptions';
import type { SolanaRpcResponse } from '@solana/rpc-types';
import type { ReactiveStreamStore } from '@solana/subscribable';
/**
 * Configuration for {@link createReactiveStoreWithInitialValueAndSlotTracking}. Pairs a one-shot
 * RPC fetch with an ongoing subscription so the resulting store can hydrate from the initial
 * response and keep up to date with notifications, slot-deduplicating the two streams.
 *
 * @typeParam TRpcValue - The value type returned by `rpcRequest` (inside the {@link SolanaRpcResponse} envelope).
 * @typeParam TSubscriptionValue - The value type emitted by `rpcSubscriptionRequest` (inside the {@link SolanaRpcResponse} envelope).
 * @typeParam TItem - The unified item type the store holds, produced by the two value mappers.
 *
 * @see {@link createReactiveStoreWithInitialValueAndSlotTracking}
 */
export type CreateReactiveStoreWithInitialValueAndSlotTrackingConfig<TRpcValue, TSubscriptionValue, TItem> = Readonly<{
    /**
     * Triggering this abort signal will cancel the pending RPC request and subscription, and
     * disconnect the store from further updates.
     */
    abortSignal: AbortSignal;
    /**
     * A pending RPC request whose response will be used to set the store's initial state.
     * The response must be a {@link SolanaRpcResponse} so that its slot can be compared with
     * subscription notifications.
     */
    rpcRequest: PendingRpcRequest<SolanaRpcResponse<TRpcValue>>;
    /**
     * A pending RPC subscription request whose notifications will be used to keep the store
     * up to date. Each notification must be a {@link SolanaRpcResponse} so that its slot can be
     * compared with the initial RPC response and other notifications.
     */
    rpcSubscriptionRequest: PendingRpcSubscriptionsRequest<SolanaRpcResponse<TSubscriptionValue>>;
    /**
     * Maps the value from a subscription notification to the item type stored in the reactive store.
     */
    rpcSubscriptionValueMapper: (value: TSubscriptionValue) => TItem;
    /**
     * Maps the value from the RPC response to the item type stored in the reactive store.
     */
    rpcValueMapper: (value: TRpcValue) => TItem;
}>;
/**
 * Creates a {@link ReactiveStreamStore} that combines an initial RPC fetch with an ongoing subscription
 * to keep its state up to date.
 *
 * The store uses slot-based comparison to ensure that only the most recent value is kept,
 * regardless of whether it came from the initial RPC response or a subscription notification.
 * This prevents stale data from overwriting newer data when the RPC response and subscription
 * notifications arrive out of order.
 *
 * Things to note:
 *
 * - `getUnifiedState()` starts in `status: 'loading'` until the first response or notification
 *   arrives. Once data arrives it transitions to `status: 'loaded'` with a
 *   {@link SolanaRpcResponse} containing the value and the slot context at which it was observed.
 * - On error from either source, the store transitions to `status: 'error'` preserving the last
 *   known value. Only the first error per connection window is captured.
 * - Calling {@link ReactiveStreamStore.retry | `retry()`} while in `status: 'error'` re-sends the RPC
 *   request and re-subscribes to the subscription using a fresh inner abort signal. The store
 *   transitions through `status: 'retrying'` back to `loaded`/`error`.
 * - Triggering the caller's abort signal disconnects the store permanently; subsequent `retry()`
 *   calls are no-ops.
 *
 * @param config
 *
 * @example
 * ```ts
 * import {
 *     address,
 *     createReactiveStoreWithInitialValueAndSlotTracking,
 *     createSolanaRpc,
 *     createSolanaRpcSubscriptions,
 * } from '@solana/kit';
 *
 * const rpc = createSolanaRpc('http://127.0.0.1:8899');
 * const rpcSubscriptions = createSolanaRpcSubscriptions('ws://127.0.0.1:8900');
 * const myAddress = address('FnHyam9w4NZoWR6mKN1CuGBritdsEWZQa4Z4oawLZGxa');
 *
 * const balanceStore = createReactiveStoreWithInitialValueAndSlotTracking({
 *     abortSignal: AbortSignal.timeout(60_000),
 *     rpcRequest: rpc.getBalance(myAddress, { commitment: 'confirmed' }),
 *     rpcValueMapper: lamports => lamports,
 *     rpcSubscriptionRequest: rpcSubscriptions.accountNotifications(myAddress),
 *     rpcSubscriptionValueMapper: ({ lamports }) => lamports,
 * });
 *
 * const unsubscribe = balanceStore.subscribe(() => {
 *     const state = balanceStore.getUnifiedState();
 *     if (state.status === 'error') {
 *         console.error('Error:', state.error);
 *         balanceStore.retry();
 *     } else if (state.status === 'loaded') {
 *         console.log(`Balance at slot ${state.data.context.slot}:`, state.data.value);
 *     }
 * });
 * ```
 *
 * @see {@link ReactiveStreamStore}
 */
export declare function createReactiveStoreWithInitialValueAndSlotTracking<TRpcValue, TSubscriptionValue, TItem>({ abortSignal, rpcRequest, rpcValueMapper, rpcSubscriptionRequest, rpcSubscriptionValueMapper, }: CreateReactiveStoreWithInitialValueAndSlotTrackingConfig<TRpcValue, TSubscriptionValue, TItem>): ReactiveStreamStore<SolanaRpcResponse<TItem>>;
//# sourceMappingURL=create-reactive-store-with-initial-value-and-slot-tracking.d.ts.map
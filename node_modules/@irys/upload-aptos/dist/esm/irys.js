import { Network } from '@aptos-labs/ts-sdk';
import BaseAptosToken from './token.js';
export class AptosToken extends BaseAptosToken {
    constructor(config) {
        super({
            name: 'aptos',
            ticker: 'APT',
            ...config,
            providerUrl: config.providerUrl ?? Network.MAINNET,
        });
    }
}
// export function AptosBundlerIrys() {
//     return new Builder(AptosToken)/* .withTokenOptions(opts) */
// }
// export default AptosBundlerIrys
export const Aptos = AptosToken;
export default Aptos;
//# sourceMappingURL=irys.js.map
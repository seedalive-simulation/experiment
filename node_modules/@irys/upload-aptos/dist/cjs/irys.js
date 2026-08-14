"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Aptos = exports.AptosToken = void 0;
const tslib_1 = require("tslib");
const ts_sdk_1 = require("@aptos-labs/ts-sdk");
const token_1 = tslib_1.__importDefault(require("./token"));
class AptosToken extends token_1.default {
    constructor(config) {
        super({
            name: 'aptos',
            ticker: 'APT',
            ...config,
            providerUrl: config.providerUrl ?? ts_sdk_1.Network.MAINNET,
        });
    }
}
exports.AptosToken = AptosToken;
// export function AptosBundlerIrys() {
//     return new Builder(AptosToken)/* .withTokenOptions(opts) */
// }
// export default AptosBundlerIrys
exports.Aptos = AptosToken;
exports.default = exports.Aptos;
//# sourceMappingURL=irys.js.map
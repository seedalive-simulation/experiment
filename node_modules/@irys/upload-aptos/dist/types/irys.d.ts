import BaseAptosToken from './token';
import { Constructable, type TokenConfigTrimmed } from '@irys/upload/builder';
import { BaseNodeToken } from '@irys/upload/esm/tokens/base';
export declare class AptosToken extends BaseAptosToken {
    constructor(config: TokenConfigTrimmed);
}
export declare const Aptos: Constructable<[TokenConfigTrimmed], BaseNodeToken>;
export default Aptos;

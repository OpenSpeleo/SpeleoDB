import { mergeDepthDomains } from './depth.js';

describe('mergeDepthDomains', () => {
    it('returns null for empty array', () => {
        expect(mergeDepthDomains([])).toBeNull();
    });

    it('returns null when all entries are null', () => {
        expect(mergeDepthDomains([null, null])).toBeNull();
    });

    it('returns single domain when only one is non-null', () => {
        expect(mergeDepthDomains([{ min: 0, max: 50 }, null])).toEqual({ min: 0, max: 50 });
    });

    it('merges multiple domains taking max of maxes', () => {
        expect(mergeDepthDomains([{ min: 0, max: 30 }, { min: 0, max: 80 }])).toEqual({ min: 0, max: 80 });
    });

    it('always returns min 0 regardless of input mins', () => {
        expect(mergeDepthDomains([{ min: -20, max: 10 }, { min: 5, max: 40 }])).toEqual({ min: 0, max: 40 });
    });
});


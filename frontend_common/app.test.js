import { captureInitialControllerState, readControllerContext } from './app.js';

describe('Vite application bootstrap', () => {
    it('parses inert JSON controller context', () => {
        const element = document.createElement('script');
        element.dataset.speleodbController = 'example';
        element.textContent = '{"enabled":true,"count":2}';
        expect(readControllerContext(element)).toEqual({ enabled: true, count: 2 });
    });

    it('rejects executable or malformed controller context', () => {
        const element = document.createElement('script');
        element.dataset.speleodbController = 'example';
        element.textContent = 'window.alert(1)';
        expect(() => readControllerContext(element)).toThrow(
            'Invalid JSON context for controller "example"'
        );
    });

    it('captures parser-time particle dimensions before lazy controllers load', () => {
        const container = document.createElement('div');
        const canvas = document.createElement('canvas');
        canvas.dataset.particleAnimation = '';
        Object.defineProperties(container, {
            offsetWidth: { value: 640 },
            offsetHeight: { value: 480 },
        });
        container.append(canvas);
        document.body.append(container);

        captureInitialControllerState(document);

        expect(canvas.dataset.initialParticleWidth).toBe('640');
        expect(canvas.dataset.initialParticleHeight).toBe('480');
    });
});

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { initPublicShell } from './main.ts';
import { ParticleAnimation } from './animation/particle-animation.ts';
import { Highlighter } from './animation/highlighter.ts';
import type { SwiperOptions } from '../../../ts-types/domain/public-shell.ts';
import type { MockInstance } from 'vitest';

type CarouselElement = HTMLElement & {
    swiper?: { initialized: boolean; params: SwiperOptions; destroy(deleteInstance: boolean, cleanStyles: boolean): void };
};
beforeAll(() => {
    for (const vendor of ['aos.js', 'swiper-bundle.min.js']) {
        (0, eval)(readFileSync(resolve('frontend_public/static/ts/vendors', vendor), 'utf8'));
    }
});
let getContext: MockInstance<HTMLCanvasElement['getContext']>;
function drawingContext() {
    return {
        scale: vi.fn(), translate: vi.fn(), beginPath: vi.fn(), arc: vi.fn<CanvasRenderingContext2D['arc']>(), fill: vi.fn(),
        setTransform: vi.fn(), clearRect: vi.fn(), fillStyle: '',
    };
}
let listeners: Array<[string, EventListenerOrEventListenerObject, boolean | AddEventListenerOptions | undefined]>;
let context: ReturnType<typeof drawingContext>;
let frameRequests: MockInstance<typeof window.requestAnimationFrame>;
beforeEach(() => {
    listeners = [];
    context = drawingContext();
    // jsdom has no canvas renderer. Only the drawing surface is substituted;
    // particle generation, real RAF scheduling and event handling stay intact.
    getContext = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as unknown as CanvasRenderingContext2D);
    // Forward real scheduling and registration while retaining resource handles
    // for cleanup; the animation API has no destroy method.
    frameRequests = vi.spyOn(window, 'requestAnimationFrame');
    const add = window.addEventListener.bind(window);
    vi.spyOn(window, 'addEventListener').mockImplementation((type, handler, options) => {
        listeners.push([type, handler, options]); add(type, handler, options);
    });
    document.body.innerHTML = '';
});
afterEach(() => {
    for (const carousel of document.querySelectorAll<CarouselElement>('.clients-carousel, .testimonials-carousel')) {
        carousel.swiper?.destroy(true, true);
    }
    for (const [type, handler, options] of listeners) window.removeEventListener(type, handler, options);
    for (const result of frameRequests.mock.results) {
        if (result.type === 'return') cancelAnimationFrame(result.value);
    }
    vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = '';
});

function canvas({ width = '100', height = '80', quantity = '1', extra = '' } = {}) {
    document.body.innerHTML = `<div><canvas data-particle-animation data-initial-particle-width="${width}" data-initial-particle-height="${height}" data-particle-quantity="${quantity}" ${extra}></canvas></div>`;
    const element = document.querySelector('canvas')!;
    Object.defineProperties(element.parentElement, { offsetWidth: { value: 120 }, offsetHeight: { value: 90 } });
    return element;
}

it('initializes AOS immediately but does not require Swiper without matching carousels', () => {
    vi.stubGlobal('Swiper', undefined);
    expect(initPublicShell()).toBeUndefined();
    expect(document.body.getAttribute('data-aos-easing')).toBe('ease-out-cubic');
    expect(document.body.getAttribute('data-aos-duration')).toBe('1000');
    expect(frameRequests).toHaveBeenCalledTimes(0);
});

it('initializes the actual carousel runtime with each family configuration', () => {
    const slides = '<div class="swiper-wrapper"><div class="swiper-slide">One</div><div class="swiper-slide">Two</div><div class="swiper-slide">Three</div></div>';
    document.body.innerHTML = `<div class="clients-carousel">${slides}</div><div class="testimonials-carousel">${slides}</div>`;
    initPublicShell();
    const clients = document.querySelector<CarouselElement>('.clients-carousel')!.swiper!;
    const testimonials = document.querySelector<CarouselElement>('.testimonials-carousel')!.swiper!;
    expect(clients.initialized).toBe(true);
    expect(clients.params).toMatchObject({ slidesPerView: 'auto', spaceBetween: 64, loop: true, speed: 5000, autoplay: { delay: 0, disableOnInteraction: true } });
    expect(testimonials.initialized).toBe(true);
    expect(testimonials.params).toMatchObject({ loop: false, spaceBetween: 24, navigation: { nextEl: '.carousel-next', prevEl: '.carousel-prev' } });
});

it('propagates missing required vendors synchronously', () => {
    const aos = AOS;
    vi.stubGlobal('AOS', undefined);
    expect(() => initPublicShell()).toThrow(TypeError);
    vi.stubGlobal('AOS', aos);
    vi.stubGlobal('Swiper', undefined);
    document.body.innerHTML = '<div class="clients-carousel"></div>';
    expect(() => initPublicShell()).toThrow(TypeError);
});

it('consumes captured dimensions once, scales the context, and preserves the RAF callback identity', async () => {
    const element = canvas();
    vi.stubGlobal('devicePixelRatio', 2);
    initPublicShell();
    expect(element.width).toBe(200); expect(element.height).toBe(160);
    expect(element.style.width).toBe('100px'); expect(element.style.height).toBe('80px');
    expect(element.dataset.initialParticleWidth).toBeUndefined(); expect(element.dataset.initialParticleHeight).toBeUndefined();
    expect(context.scale).toHaveBeenCalledWith(2, 2);
    const [x, y, radius, start, end] = context.arc.mock.calls[0]!;
    expect(x).toBeGreaterThanOrEqual(0); expect(x).toBeLessThan(100);
    expect(y).toBeGreaterThanOrEqual(0); expect(y).toBeLessThan(80);
    expect([1, 2]).toContain(radius); expect(start).toBe(0); expect(end).toBe(2 * Math.PI);
    const frame = frameRequests.mock.calls[0]![0];
    await new Promise(requestAnimationFrame);
    expect(frameRequests.mock.calls.at(-1)![0]).toBe(frame);
    window.dispatchEvent(new Event('resize'));
    expect(element.width).toBe(240); expect(element.height).toBe(180);
    expect(frameRequests).toHaveBeenCalledTimes(3);
});

it('rounds the edge remapping before numeric alpha multiplication', () => {
    const animation = new ParticleAnimation(canvas({ width: '10', height: '10' }), { quantity: 0 });
    animation.circles.push({
        x: 5, y: 5, translateX: 0, translateY: 0, size: 1,
        alpha: 0, targetAlpha: 0.3, dx: 0, dy: 0, magnetism: 1,
    });
    animation.animate();
    expect(context.fillStyle).toBe('rgba(255, 255, 255, 0.06)');
});

it('uses parent dimensions for invalid captures and preserves empty/invalid quantity semantics', () => {
    const element = canvas({ width: 'invalid', height: '0', quantity: '' });
    initPublicShell(); expect(element.width).toBe(120); expect(element.height).toBe(90);
    expect(context.arc).not.toHaveBeenCalled(); expect(frameRequests).toHaveBeenCalledTimes(1);
    element.dataset.particleQuantity = 'invalid'; initPublicShell();
    expect(context.arc).not.toHaveBeenCalled(); expect(frameRequests).toHaveBeenCalledTimes(2);
});

it('uses quantity defaults only when the attribute is absent', () => {
    const element = canvas(); delete element.dataset.particleQuantity;
    initPublicShell(); expect(context.arc).toHaveBeenCalledTimes(60);
});

it('preserves missing-context failure and creates no animation frame after that failure', () => {
    canvas(); getContext.mockReturnValue(null);
    expect(() => initPublicShell()).toThrow(TypeError); expect(frameRequests).toHaveBeenCalledTimes(0);
});

it('updates highlighter variables only strictly inside and retains the original box set', () => {
    document.body.innerHTML = '<div data-highlighter><article></article></div>';
    const container = document.querySelector<HTMLElement>('[data-highlighter]')!; const box = container.firstElementChild as HTMLElement;
    Object.defineProperties(container, { offsetWidth: { value: 100 }, offsetHeight: { value: 80 } });
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(new DOMRect(10, 20));
    vi.spyOn(box, 'getBoundingClientRect').mockReturnValue(new DOMRect(20, 30));
    initPublicShell();
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 40, clientY: 60 }));
    expect(box.style.getPropertyValue('--mouse-x')).toBe('20px'); expect(box.style.getPropertyValue('--mouse-y')).toBe('30px');
    container.insertAdjacentHTML('beforeend', '<aside></aside>');
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 10, clientY: 20 }));
    expect(box.style.getPropertyValue('--mouse-x')).toBe('20px');
    expect((container.lastElementChild as HTMLElement).style.getPropertyValue('--mouse-x')).toBe('');
    window.dispatchEvent(new Event('resize'));
});

it('repeated initialization creates fresh animation state and listeners', () => {
    canvas(); initPublicShell(); initPublicShell();
    expect(frameRequests).toHaveBeenCalledTimes(2); expect(frameRequests.mock.calls[0]![0]).not.toBe(frameRequests.mock.calls[1]![0]);
    expect(listeners.filter(([type]) => type === 'mousemove')).toHaveLength(2);
});

it('creates particle parameters within the actual canvas and motion bounds', () => {
    const animation = new ParticleAnimation(canvas({ quantity: '0' }), { quantity: 0 });
    const circle = animation.circleParams();
    expect(circle.x).toBeGreaterThanOrEqual(0); expect(circle.x).toBeLessThan(100);
    expect(circle.y).toBeGreaterThanOrEqual(0); expect(circle.y).toBeLessThan(80);
    expect([1, 2]).toContain(circle.size);
    expect(circle.targetAlpha).toBeGreaterThanOrEqual(0.1); expect(circle.targetAlpha).toBeLessThanOrEqual(0.7);
    expect(Math.abs(circle.dx)).toBeLessThanOrEqual(0.1); expect(Math.abs(circle.dy)).toBeLessThanOrEqual(0.1);
    expect(circle.magnetism).toBeGreaterThanOrEqual(0.1); expect(circle.magnetism).toBeLessThan(4.1);
});

it('constructs highlighters immediately with independent captured boxes and bound listeners', () => {
    document.body.innerHTML = '<div><article></article></div><section><aside></aside></section>';
    const first = new Highlighter(document.querySelector('div')!);
    const second = new Highlighter(document.querySelector('section')!);
    expect(first.boxes).toEqual([document.querySelector('article')]);
    expect(second.boxes).toEqual([document.querySelector('aside')]);
    expect(first.mouse).not.toBe(second.mouse);
    expect(listeners.map(([type]) => type)).toEqual(['resize', 'mousemove', 'resize', 'mousemove']);
    expect(first).toHaveProperty('initContainer', listeners[0]![1]);
    expect(first).toHaveProperty('onMouseMove', listeners[1]![1]);
    expect(second).toHaveProperty('initContainer', listeners[2]![1]);
    expect(second).toHaveProperty('onMouseMove', listeners[3]![1]);
});

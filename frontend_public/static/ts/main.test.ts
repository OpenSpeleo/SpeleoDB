import { initPublicShell } from './main.ts';
import { ParticleAnimation } from './animation/particle-animation.ts';
import { Highlighter } from './animation/highlighter.ts';
import type { SwiperOptions } from '../../../ts-types/domain/public-shell.ts';
import type { MockInstance } from 'vitest';

const swiper = vi.fn(function (_selector: string, _options: SwiperOptions) {});
const aosInit = vi.fn();
let getContext: MockInstance<HTMLCanvasElement['getContext']>;
function drawingContext() {
    return {
        scale: vi.fn(), translate: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(),
        setTransform: vi.fn(), clearRect: vi.fn(), fillStyle: '',
    };
}
let listeners: Array<[string, EventListenerOrEventListenerObject]>;
let context: ReturnType<typeof drawingContext>;
let frames: FrameRequestCallback[];
beforeEach(() => {
    listeners = [];
    frames = [];
    context = drawingContext();
    aosInit.mockClear(); vi.stubGlobal('AOS', { init: aosInit });
    swiper.mockClear(); vi.stubGlobal('Swiper', swiper);
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    getContext = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as unknown as CanvasRenderingContext2D);
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => { frames.push(callback); return frames.length; });
    const add = window.addEventListener.bind(window);
    vi.spyOn(window, 'addEventListener').mockImplementation((type, handler, options) => {
        listeners.push([type, handler]); add(type, handler, options);
    });
    document.body.innerHTML = '';
});
afterEach(() => {
    for (const [type, handler] of listeners) window.removeEventListener(type, handler);
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
    expect(aosInit).toHaveBeenCalledWith({ once: true, disable: 'phone', duration: 1000, easing: 'ease-out-cubic' });
    expect(aosInit.mock.contexts[0]).toBe(AOS);
    expect(frames).toHaveLength(0);
});

it('constructs one swiper per matching family with its distinct options', () => {
    document.body.innerHTML = '<div class="clients-carousel"></div><div class="clients-carousel"></div><div class="testimonials-carousel"></div>';
    initPublicShell();
    expect(Swiper).toHaveBeenCalledTimes(2);
    expect(swiper.mock.calls[0]).toEqual(['.clients-carousel', expect.objectContaining({ slidesPerView: 'auto', spaceBetween: 64, loop: true, speed: 5000, autoplay: { delay: 0, disableOnInteraction: true } })]);
    expect(swiper.mock.calls[1]).toEqual(['.testimonials-carousel', expect.objectContaining({ loop: false, spaceBetween: 24, navigation: { nextEl: '.carousel-next', prevEl: '.carousel-prev' } })]);
});

it('propagates missing required vendors synchronously', () => {
    vi.stubGlobal('AOS', undefined);
    expect(() => initPublicShell()).toThrow(TypeError);
    vi.stubGlobal('AOS', { init: vi.fn() });
    vi.stubGlobal('Swiper', undefined);
    document.body.innerHTML = '<div class="clients-carousel"></div>';
    expect(() => initPublicShell()).toThrow(TypeError);
});

it('consumes captured dimensions once, scales the context, and preserves the RAF callback identity', () => {
    const element = canvas();
    vi.stubGlobal('devicePixelRatio', 2);
    initPublicShell();
    expect(element.width).toBe(200); expect(element.height).toBe(160);
    expect(element.style.width).toBe('100px'); expect(element.style.height).toBe('80px');
    expect(element.dataset.initialParticleWidth).toBeUndefined(); expect(element.dataset.initialParticleHeight).toBeUndefined();
    expect(context.scale).toHaveBeenCalledWith(2, 2);
    expect(context.arc).toHaveBeenCalledWith(50, 40, 2, 0, 2 * Math.PI);
    expect(context.fillStyle).toBe('rgba(255, 255, 255, 0.02)');
    const frame = frames[0]!; frame(16);
    expect(frames[1]).toBe(frame); expect(context.fillStyle).toBe('rgba(255, 255, 255, 0.04)');
    window.dispatchEvent(new Event('resize'));
    expect(element.width).toBe(240); expect(element.height).toBe(180);
    expect(frames).toHaveLength(2);
});

it('rounds the edge remapping before numeric alpha multiplication', () => {
    canvas({ width: '10', height: '10' }); initPublicShell();
    expect(context.fillStyle).toBe('rgba(255, 255, 255, 0.06)');
});

it('uses parent dimensions for invalid captures and preserves empty/invalid quantity semantics', () => {
    const element = canvas({ width: 'invalid', height: '0', quantity: '' });
    initPublicShell(); expect(element.width).toBe(120); expect(element.height).toBe(90);
    expect(context.arc).not.toHaveBeenCalled(); expect(frames).toHaveLength(1);
    element.dataset.particleQuantity = 'invalid'; initPublicShell();
    expect(context.arc).not.toHaveBeenCalled(); expect(frames).toHaveLength(2);
});

it('uses quantity defaults only when the attribute is absent', () => {
    const element = canvas(); delete element.dataset.particleQuantity;
    initPublicShell(); expect(context.arc).toHaveBeenCalledTimes(60);
});

it('preserves missing-context failure and creates no animation frame after that failure', () => {
    canvas(); getContext.mockReturnValue(null);
    expect(() => initPublicShell()).toThrow(TypeError); expect(frames).toHaveLength(0);
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
    expect(frames).toHaveLength(2); expect(frames[0]).not.toBe(frames[1]);
    expect(listeners.filter(([type]) => type === 'mousemove')).toHaveLength(2);
});

it('exposes particle construction without changing random sampling order or bound receiver identity', () => {
    const element = canvas({ quantity: '0' });
    const animation = new ParticleAnimation(element, { quantity: 0 });
    const random = vi.mocked(Math.random);
    random.mockClear();
    for (const value of [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]) random.mockReturnValueOnce(value);
    expect(animation.circleParams()).toEqual({
        x: 10, y: 16, translateX: 0, translateY: 0, size: 1,
        alpha: 0, targetAlpha: 0.3, dx: 0, dy: (0.6 - 0.5) * 0.2,
        magnetism: 0.1 + 0.7 * 4,
    });
    expect(random).toHaveBeenCalledTimes(7);
    expect(animation).toHaveProperty('animate', frames[0]);
    expect(Object.hasOwn(animation, 'drawCircle')).toBe(true);
    expect(Object.hasOwn(animation, 'clearContext')).toBe(false);
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

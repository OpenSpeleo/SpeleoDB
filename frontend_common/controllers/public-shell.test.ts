import type { MockInstance } from 'vitest';
import type { SwiperOptions } from '../../ts-types/domain/public-shell.ts';
import { init } from './public-shell.ts';

let listeners: Array<[string, EventListenerOrEventListenerObject, boolean | AddEventListenerOptions | undefined]>;
const aosInit = vi.fn();
const swiper = vi.fn(function (_selector: string, _options: SwiperOptions) {});
let animationFrame: MockInstance<typeof window.requestAnimationFrame>;

beforeEach(() => {
    document.body.innerHTML = '';
    aosInit.mockReset(); vi.stubGlobal('AOS', { init: aosInit });
    swiper.mockReset(); vi.stubGlobal('Swiper', swiper);
    animationFrame = vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    listeners = [];
    const addEventListener = window.addEventListener.bind(window);
    vi.spyOn(window, 'addEventListener').mockImplementation((name, callback, options) => {
        listeners.push([name, callback, options]);
        addEventListener(name, callback, options);
    });
});

afterEach(() => {
    for (const [name, callback, options] of listeners) window.removeEventListener(name, callback, options);
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
});

it('initializes AOS immediately without context or waiting for load and resolves undefined', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init();
    expect(aosInit).toHaveBeenCalledWith({ once: true, disable: 'phone', duration: 1000, easing: 'ease-out-cubic' });
    expect(aosInit.mock.contexts[0]).toBe(AOS);
    expect(Swiper).not.toHaveBeenCalled();
    expect(animationFrame).not.toHaveBeenCalled();
    await expect(pending).resolves.toBeUndefined();
});

it('constructs only present carousel families with their distinct options', async () => {
    document.body.innerHTML = '<div class="clients-carousel"></div><div class="testimonials-carousel"></div>';
    await init();
    expect(Swiper).toHaveBeenCalledTimes(2);
    expect(swiper.mock.calls[0]).toEqual(['.clients-carousel', {
        slidesPerView: 'auto', spaceBetween: 64, centeredSlides: true, loop: true,
        speed: 5000, noSwiping: true, noSwipingClass: 'swiper-slide',
        autoplay: { delay: 0, disableOnInteraction: true },
    }]);
    expect(swiper.mock.calls[1]).toEqual(['.testimonials-carousel', {
        breakpoints: { 320: { slidesPerView: 1 }, 640: { slidesPerView: 2 }, 1024: { slidesPerView: 3 } },
        grabCursor: true, loop: false, centeredSlides: false, initialSlide: 0, spaceBetween: 24,
        navigation: { nextEl: '.carousel-next', prevEl: '.carousel-prev' },
    }]);
});

it('does not require Swiper on pages without carousels but rejects if a carousel needs it', async () => {
    vi.stubGlobal('Swiper', undefined);
    await expect(init()).resolves.toBeUndefined();
    document.body.innerHTML = '<div class="clients-carousel"></div>';
    await expect(init()).rejects.toThrow(TypeError);
});

it('rejects a synchronous AOS failure and stops subsequent initialization', async () => {
    const error = new Error('AOS unavailable');
    aosInit.mockImplementation(() => { throw error; });
    document.body.innerHTML = '<div class="clients-carousel"></div>';
    await expect(init()).rejects.toBe(error);
    expect(Swiper).not.toHaveBeenCalled();
});

it('rejects when the required AOS global is missing', async () => {
    vi.stubGlobal('AOS', undefined);
    await expect(init()).rejects.toThrow(TypeError);
});

it('repeats vendor construction when initialized twice', async () => {
    document.body.innerHTML = '<div class="clients-carousel"></div>';
    await init();
    await init();
    expect(aosInit).toHaveBeenCalledTimes(2);
    expect(Swiper).toHaveBeenCalledTimes(2);
});

it('consumes captured particle dimensions once, draws immediately, and retains its bound RAF and resize handlers', async () => {
    document.body.innerHTML = '<div><canvas data-particle-animation data-particle-quantity="1" data-particle-staticity="50" data-particle-ease="50" data-initial-particle-width="200" data-initial-particle-height="100"></canvas></div>';
    const canvas = document.querySelector('canvas')!;
    Object.defineProperties(canvas.parentElement, {
        offsetWidth: { configurable: true, value: 300 },
        offsetHeight: { configurable: true, value: 150 },
    });
    const context = {
        scale: vi.fn(), translate: vi.fn(), beginPath: vi.fn(), arc: vi.fn(),
        fill: vi.fn(), setTransform: vi.fn(), clearRect: vi.fn(), fillStyle: '',
    };
    vi.spyOn(canvas, 'getContext').mockReturnValue(context as unknown as CanvasRenderingContext2D);
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    vi.spyOn(window, 'devicePixelRatio', 'get').mockReturnValue(2);
    await init();
    expect(canvas.width).toBe(400);
    expect(canvas.height).toBe(200);
    expect(canvas.style.width).toBe('200px');
    expect(canvas.style.height).toBe('100px');
    expect(canvas.dataset.initialParticleWidth).toBeUndefined();
    expect(canvas.dataset.initialParticleHeight).toBeUndefined();
    expect(context.scale).toHaveBeenCalledWith(2, 2);
    expect(context.arc).toHaveBeenCalledTimes(2);
    expect(context.fillStyle).toBe('rgba(255, 255, 255, 0.02)');
    expect(animationFrame).toHaveBeenCalledOnce();
    const animate = animationFrame.mock.calls[0]![0];
    animate(0);
    expect(animationFrame.mock.calls[1]![0]).toBe(animate);
    window.dispatchEvent(new Event('resize'));
    expect(canvas.width).toBe(600);
    expect(canvas.height).toBe(300);
    expect(listeners.map(([name]) => name)).toEqual(['resize', 'mousemove']);
});

it('updates each highlighter child relative to its bounds only for interior mouse positions', async () => {
    document.body.innerHTML = '<div data-highlighter><div></div><div></div></div>';
    const highlighter = document.querySelector<HTMLElement>('[data-highlighter]')!;
    const [first, second] = Array.from(highlighter.children) as [HTMLElement, HTMLElement];
    Object.defineProperties(highlighter, {
        offsetWidth: { configurable: true, value: 100 },
        offsetHeight: { configurable: true, value: 100 },
    });
    vi.spyOn(highlighter, 'getBoundingClientRect').mockReturnValue(new DOMRect(10, 20));
    vi.spyOn(first, 'getBoundingClientRect').mockReturnValue(new DOMRect(15, 25));
    vi.spyOn(second, 'getBoundingClientRect').mockReturnValue(new DOMRect(35, 45));
    await init();
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 60, clientY: 70 }));
    expect(first.style.getPropertyValue('--mouse-x')).toBe('45px');
    expect(first.style.getPropertyValue('--mouse-y')).toBe('45px');
    expect(second.style.getPropertyValue('--mouse-x')).toBe('25px');
    expect(second.style.getPropertyValue('--mouse-y')).toBe('25px');
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 10, clientY: 20 }));
    expect(first.style.getPropertyValue('--mouse-x')).toBe('45px');
    expect(listeners.map(([name]) => name)).toEqual(['resize', 'mousemove']);
});

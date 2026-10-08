import { ParticleAnimation } from './animation/particle-animation.ts';
import { Highlighter } from './animation/highlighter.ts';

export function initPublicShell() {
AOS.init({
  once: true,
  disable: 'phone',
  duration: 1000,
  easing: 'ease-out-cubic',
});

const clientsEl = document.querySelectorAll('.clients-carousel');
if (clientsEl.length > 0) {
  const clients = new Swiper('.clients-carousel', {
    slidesPerView: 'auto',
    spaceBetween: 64,
    centeredSlides: true,
    loop: true,
    speed: 5000,
    noSwiping: true,
    noSwipingClass: 'swiper-slide',
    autoplay: {
      delay: 0,
      disableOnInteraction: true,
    },
  });
}

const carouselEl = document.querySelectorAll('.testimonials-carousel');
if (carouselEl.length > 0) {
  const carousel = new Swiper('.testimonials-carousel', {
    breakpoints: {
      320: {
        slidesPerView: 1
      },
      640: {
        slidesPerView: 2
      },
      1024: {
        slidesPerView: 3
      }
    },
    grabCursor: true,
    loop: false,
    centeredSlides: false,
    initialSlide: 0,
    spaceBetween: 24,
    navigation: {
      nextEl: '.carousel-next',
      prevEl: '.carousel-prev',
    },
  });
}

// Init ParticleAnimation
const canvasElements = document.querySelectorAll<HTMLCanvasElement>('[data-particle-animation]');
canvasElements.forEach(canvas => {
  const options = {
    quantity: canvas.dataset.particleQuantity,
    staticity: canvas.dataset.particleStaticity,
    ease: canvas.dataset.particleEase,
  };
  new ParticleAnimation(canvas, options);
});


// Init Highlighter
const highlighters = document.querySelectorAll<HTMLElement>('[data-highlighter]');
highlighters.forEach((highlighter) => {
  new Highlighter(highlighter);
});
}

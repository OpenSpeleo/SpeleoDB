// Box highlighter
export class Highlighter {
  declare container: HTMLElement;
  declare boxes: HTMLElement[];
  declare mouse: { x: number; y: number };
  declare containerSize: { w: number; h: number };

  constructor(containerElement: HTMLElement) {
    this.container = containerElement;
    this.boxes = Array.from(this.container.children) as HTMLElement[];
    this.mouse = {
      x: 0,
      y: 0,
    };
    this.containerSize = {
      w: 0,
      h: 0,
    };
    this.initContainer = this.initContainer.bind(this);
    this.onMouseMove = this.onMouseMove.bind(this);
    this.init();
  }

  initContainer() {
    this.containerSize.w = this.container.offsetWidth;
    this.containerSize.h = this.container.offsetHeight;
  }

  onMouseMove(event: MouseEvent) {
    const { clientX, clientY } = event;
    const rect = this.container.getBoundingClientRect();
    const { w, h } = this.containerSize;
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    const inside = x < w && x > 0 && y < h && y > 0;
    if (inside) {
      this.mouse.x = x;
      this.mouse.y = y;
      this.boxes.forEach((box) => {
        const boxX = -(box.getBoundingClientRect().left - rect.left) + this.mouse.x;
        const boxY = -(box.getBoundingClientRect().top - rect.top) + this.mouse.y;
        box.style.setProperty('--mouse-x', `${boxX}px`);
        box.style.setProperty('--mouse-y', `${boxY}px`);
      });
    }
  }

  init() {
    this.initContainer();
    // eslint-disable-next-line @typescript-eslint/unbound-method -- Bound once in the constructor; retain listener identity.
    window.addEventListener('resize', this.initContainer);
    // eslint-disable-next-line @typescript-eslint/unbound-method -- Bound once in the constructor; retain listener identity.
    window.addEventListener('mousemove', this.onMouseMove);
  }
}

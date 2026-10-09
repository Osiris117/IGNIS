const el = document.querySelector('.env-chip[data-env="pyro"]');
let frames = 0;
const boxes = [];
const t0 = performance.now();
return await new Promise(res => {
  function loop() {
    frames++;
    if (frames % 10 === 0) boxes.push(JSON.stringify(el.getBoundingClientRect()));
    if (performance.now() - t0 < 2000) requestAnimationFrame(loop);
    else res({ fps: Math.round(frames / 2), distintas: new Set(boxes).size });
  }
  requestAnimationFrame(loop);
});

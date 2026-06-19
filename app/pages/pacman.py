import streamlit as st
import streamlit.components.v1 as components

st.title("パックマン")

pacman_html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {
    background: #000;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 10px;
    font-family: 'Arial', sans-serif;
    margin: 0;
  }
  #container { display: flex; gap: 20px; align-items: flex-start; }
  canvas { display: block; }
  #info { color: #fff; min-width: 130px; }
  .box {
    background: #111;
    border: 1px solid #ffff00;
    padding: 8px 12px;
    margin-bottom: 12px;
    border-radius: 4px;
  }
  .box h3 { color: #ffff00; margin: 0 0 4px; font-size: 12px; letter-spacing: 2px; }
  .val { font-size: 24px; font-weight: bold; color: #fff; }
  #lives-display { display: flex; gap: 6px; align-items: center; margin-top: 4px; }
  #start-btn {
    background: #ffff00; color: #000; border: none;
    padding: 8px 16px; font-size: 13px; font-weight: bold;
    cursor: pointer; border-radius: 4px; width: 100%; margin-top: 4px;
  }
  #start-btn:hover { background: #cccc00; }
  #msg {
    color: #ffff00; font-size: 13px; text-align: center;
    min-height: 20px; margin-top: 8px;
  }
</style>
</head>
<body>
<div id="container">
  <canvas id="c"></canvas>
  <div id="info">
    <div class="box">
      <h3>スコア</h3>
      <div class="val" id="score">0</div>
    </div>
    <div class="box">
      <h3>ハイスコア</h3>
      <div class="val" id="hi">0</div>
    </div>
    <div class="box">
      <h3>残機</h3>
      <div id="lives-display"></div>
    </div>
    <button id="start-btn" onclick="startGame()">スタート / リセット</button>
    <div id="msg">スタートボタンを押してください</div>
    <div class="box" style="margin-top:12px; font-size:11px; color:#aaa; line-height:1.8">
      <span style="color:#ffff00; font-weight:bold">← → ↑ ↓</span> 移動<br>
      <span style="color:#ffff00; font-weight:bold">P</span> 一時停止<br>
      <span style="color:#00ffff">●</span> パワーエサ：ゴーストを食べられる
    </div>
  </div>
</div>

<script>
const TILE = 16;
// 0=空, 1=壁, 2=ドット, 3=パワーエサ, 4=ゴーストハウス出口
const MAP_TEMPLATE = [
  [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
  [1,2,2,2,2,2,2,2,2,1,2,2,2,2,2,2,2,2,1],
  [1,3,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,3,1],
  [1,2,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,2,1],
  [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
  [1,2,1,1,2,1,2,1,1,1,1,1,2,1,2,1,1,2,1],
  [1,2,2,2,2,1,2,2,2,1,2,2,2,1,2,2,2,2,1],
  [1,1,1,1,2,1,1,1,0,0,0,1,1,1,2,1,1,1,1],
  [1,1,1,1,2,1,0,0,0,0,0,0,0,1,2,1,1,1,1],
  [1,1,1,1,2,1,0,1,1,4,1,1,0,1,2,1,1,1,1],
  [0,0,0,0,2,0,0,1,0,0,0,1,0,0,2,0,0,0,0],
  [1,1,1,1,2,1,0,1,1,1,1,1,0,1,2,1,1,1,1],
  [1,1,1,1,2,1,0,0,0,0,0,0,0,1,2,1,1,1,1],
  [1,1,1,1,2,1,0,1,1,1,1,1,0,1,2,1,1,1,1],
  [1,2,2,2,2,2,2,2,2,1,2,2,2,2,2,2,2,2,1],
  [1,2,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,2,1],
  [1,3,2,1,2,2,2,2,2,0,2,2,2,2,2,1,2,3,1],
  [1,1,2,1,2,1,2,1,1,1,1,1,2,1,2,1,2,1,1],
  [1,2,2,2,2,1,2,2,2,1,2,2,2,1,2,2,2,2,1],
  [1,2,1,1,1,1,1,1,2,1,2,1,1,1,1,1,1,2,1],
  [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
  [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
];
const ROWS = MAP_TEMPLATE.length;
const COLS = MAP_TEMPLATE[0].length;

const canvas = document.getElementById('c');
canvas.width  = COLS * TILE;
canvas.height = ROWS * TILE;
const ctx = canvas.getContext('2d');

let map, pacman, ghosts, score, hiScore = 0, lives, totalDots, eaten, paused, gameOver, won, animFrame, powerTimer;
let inputDir = {x:0, y:0};

const GHOST_COLORS = ['#ff0000','#ffb8ff','#00ffff','#ffb852'];
const GHOST_NAMES  = ['Blinky','Pinky','Inky','Clyde'];

function initMap() {
  map = MAP_TEMPLATE.map(r => [...r]);
  totalDots = 0;
  for (let r=0; r<ROWS; r++) for (let c=0; c<COLS; c++) {
    if (map[r][c] === 2 || map[r][c] === 3) totalDots++;
  }
}

function startGame() {
  initMap();
  score = 0; lives = 3; eaten = 0; paused = false; gameOver = false; won = false; powerTimer = 0;
  inputDir = {x:1, y:0};
  pacman = { x: 9*TILE + TILE/2, y: 16*TILE + TILE/2, dx:1, dy:0, mouthAngle: 0.25, mouthDir: 1, speed: 2 };
  ghosts = GHOST_NAMES.map((name, i) => ({
    x: (8 + i%2)*TILE + TILE/2,
    y: (i < 2 ? 9 : 10)*TILE + TILE/2,
    dx: i%2===0 ? 1 : -1, dy: 0,
    color: GHOST_COLORS[i],
    frightened: false,
    dead: false,
    scatter: i,
    timer: i * 60,
    home: true,
    exitTimer: i * 90,
  }));
  updateUI();
  document.getElementById('msg').textContent = '';
  cancelAnimationFrame(animFrame);
  loop();
}

function isWall(px, py, margin=6) {
  const checks = [
    [px - margin, py - margin],
    [px + margin, py - margin],
    [px - margin, py + margin],
    [px + margin, py + margin],
  ];
  for (const [x, y] of checks) {
    const c = Math.floor(x / TILE);
    const r = Math.floor(y / TILE);
    if (r < 0 || r >= ROWS || c < 0 || c >= COLS) return true;
    if (map[r][c] === 1) return true;
  }
  return false;
}

function tileAt(px, py) {
  const c = Math.floor(px / TILE);
  const r = Math.floor(py / TILE);
  if (r < 0 || r >= ROWS || c < 0 || c >= COLS) return -1;
  return map[r][c];
}

function eatDot(px, py) {
  const c = Math.floor(px / TILE);
  const r = Math.floor(py / TILE);
  if (r < 0 || r >= ROWS || c < 0 || c >= COLS) return;
  if (map[r][c] === 2) { map[r][c] = 0; score += 10; eaten++; }
  else if (map[r][c] === 3) {
    map[r][c] = 0; score += 50; eaten++;
    powerTimer = 300;
    ghosts.forEach(g => { if (!g.dead) g.frightened = true; });
  }
  if (eaten >= totalDots) { won = true; }
  updateUI();
}

function movePacman() {
  // 試しに入力方向へ進める
  const nx = pacman.x + inputDir.x * pacman.speed;
  const ny = pacman.y + inputDir.y * pacman.speed;
  if (!isWall(nx, ny)) {
    pacman.dx = inputDir.x;
    pacman.dy = inputDir.y;
  }
  const mx = pacman.x + pacman.dx * pacman.speed;
  const my = pacman.y + pacman.dy * pacman.speed;
  if (!isWall(mx, my)) {
    pacman.x = mx;
    pacman.y = my;
  }
  // トンネル (左右ループ)
  if (pacman.x < 0) pacman.x = COLS * TILE;
  if (pacman.x > COLS * TILE) pacman.x = 0;
  eatDot(pacman.x, pacman.y);
  // 口アニメ
  pacman.mouthAngle += 0.05 * pacman.mouthDir;
  if (pacman.mouthAngle >= 0.25) pacman.mouthDir = -1;
  if (pacman.mouthAngle <= 0.01) pacman.mouthDir = 1;
}

function ghostDirection(ghost) {
  const dirs = [{x:1,y:0},{x:-1,y:0},{x:0,y:1},{x:0,y:-1}];
  const possible = dirs.filter(d => {
    if (d.x === -ghost.dx && d.y === -ghost.dy) return false; // Uターン禁止（通常時）
    const nx = ghost.x + d.x * 2;
    const ny = ghost.y + d.y * 2;
    return !isWall(nx, ny, 4);
  });
  if (!possible.length) return {x: -ghost.dx, y: -ghost.dy};

  if (ghost.frightened) {
    return possible[Math.floor(Math.random() * possible.length)];
  }
  // 追跡：パックマンへの距離が最小の方向へ
  let best = possible[0], bestDist = Infinity;
  for (const d of possible) {
    const tx = ghost.x + d.x * TILE;
    const ty = ghost.y + d.y * TILE;
    const dist = (tx - pacman.x)**2 + (ty - pacman.y)**2;
    if (dist < bestDist) { bestDist = dist; best = d; }
  }
  return best;
}

function moveGhost(ghost) {
  if (ghost.home) {
    ghost.exitTimer--;
    if (ghost.exitTimer <= 0) ghost.home = false;
    // ゴーストハウス内で上下移動
    ghost.y += ghost.dy * 1;
    if (ghost.y > 10.5*TILE) ghost.dy = -1;
    if (ghost.y < 9.5*TILE)  ghost.dy = 1;
    if (ghost.dy === 0) ghost.dy = 1;
    return;
  }

  // グリッド中央付近で方向転換判定
  const cx = ghost.x % TILE;
  const cy = ghost.y % TILE;
  const atCenter = Math.abs(cx - TILE/2) < 2 && Math.abs(cy - TILE/2) < 2;
  if (atCenter) {
    const d = ghostDirection(ghost);
    ghost.dx = d.x; ghost.dy = d.y;
  }

  const speed = ghost.frightened ? 1 : (ghost.dead ? 3 : 1.5);
  const nx = ghost.x + ghost.dx * speed;
  const ny = ghost.y + ghost.dy * speed;
  if (!isWall(nx, ny, 4)) {
    ghost.x = nx; ghost.y = ny;
  } else {
    const d = ghostDirection(ghost);
    ghost.dx = d.x; ghost.dy = d.y;
  }
  if (ghost.x < 0) ghost.x = COLS * TILE;
  if (ghost.x > COLS * TILE) ghost.x = 0;
}

function checkCollision() {
  for (const g of ghosts) {
    if (g.home) continue;
    const dist = Math.hypot(g.x - pacman.x, g.y - pacman.y);
    if (dist < TILE - 2) {
      if (g.frightened) {
        g.frightened = false; g.dead = true;
        score += 200;
        updateUI();
        // リスポーン先へ戻す
        g.x = 9*TILE + TILE/2; g.y = 9*TILE + TILE/2;
        g.home = true; g.exitTimer = 180;
        setTimeout(() => { g.dead = false; }, 3000);
      } else if (!g.dead) {
        lives--;
        updateUI();
        if (lives <= 0) { gameOver = true; return; }
        resetPositions();
      }
    }
  }
}

function resetPositions() {
  inputDir = {x:1, y:0};
  pacman.x = 9*TILE + TILE/2; pacman.y = 16*TILE + TILE/2;
  pacman.dx = 1; pacman.dy = 0;
  powerTimer = 0;
  ghosts.forEach((g, i) => {
    g.x = (8 + i%2)*TILE + TILE/2;
    g.y = (i < 2 ? 9 : 10)*TILE + TILE/2;
    g.dx = i%2===0 ? 1 : -1; g.dy = 0;
    g.frightened = false; g.dead = false;
    g.home = true; g.exitTimer = i * 90;
  });
}

// --- 描画 ---
function drawMaze() {
  for (let r=0; r<ROWS; r++) {
    for (let c=0; c<COLS; c++) {
      const x = c*TILE, y = r*TILE;
      const t = map[r][c];
      if (t === 1) {
        ctx.fillStyle = '#1a1aff';
        ctx.fillRect(x, y, TILE, TILE);
        ctx.strokeStyle = '#0000aa';
        ctx.strokeRect(x+1, y+1, TILE-2, TILE-2);
      } else if (t === 2) {
        ctx.fillStyle = '#ffff99';
        ctx.beginPath();
        ctx.arc(x+TILE/2, y+TILE/2, 2, 0, Math.PI*2);
        ctx.fill();
      } else if (t === 3) {
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(x+TILE/2, y+TILE/2, 5, 0, Math.PI*2);
        ctx.fill();
      }
    }
  }
}

function drawPacman() {
  const p = pacman;
  const angle = Math.atan2(p.dy, p.dx);
  ctx.fillStyle = '#ffff00';
  ctx.beginPath();
  ctx.moveTo(p.x, p.y);
  ctx.arc(p.x, p.y, TILE/2 - 1, angle + p.mouthAngle * Math.PI, angle + (2 - p.mouthAngle) * Math.PI);
  ctx.closePath();
  ctx.fill();
}

function drawGhost(g) {
  const r = TILE/2 - 1;
  const x = g.x, y = g.y;
  let color = g.frightened ? (powerTimer < 100 && Math.floor(powerTimer/10)%2===0 ? '#ffffff' : '#0000ff') : g.color;
  if (g.dead) color = 'rgba(255,255,255,0.3)';

  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y - r*0.2, r, Math.PI, 0, false);
  ctx.lineTo(x + r, y + r);
  // 下のギザギザ
  const w = r * 2 / 3;
  for (let i = 0; i < 3; i++) {
    ctx.lineTo(x + r - w*(i+0.5), y + r * 0.6);
    ctx.lineTo(x + r - w*(i+1), y + r);
  }
  ctx.closePath();
  ctx.fill();

  if (!g.dead) {
    // 目
    const eyeOffsets = [-0.3, 0.3];
    for (const eo of eyeOffsets) {
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.ellipse(x + eo*r, y - r*0.3, r*0.25, r*0.35, 0, 0, Math.PI*2);
      ctx.fill();
      ctx.fillStyle = g.frightened ? '#fff' : '#00f';
      ctx.beginPath();
      ctx.arc(x + eo*r + (g.dx)*r*0.12, y - r*0.3 + (g.dy)*r*0.12, r*0.13, 0, Math.PI*2);
      ctx.fill();
    }
  }
}

function drawAll() {
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  drawMaze();
  drawPacman();
  ghosts.forEach(drawGhost);
}

function updateUI() {
  document.getElementById('score').textContent = score;
  if (score > hiScore) { hiScore = score; document.getElementById('hi').textContent = hiScore; }
  const ld = document.getElementById('lives-display');
  ld.innerHTML = '';
  for (let i=0; i<lives; i++) {
    const c = document.createElement('canvas');
    c.width = c.height = 16;
    const cx = c.getContext('2d');
    cx.fillStyle = '#ffff00';
    cx.beginPath();
    cx.moveTo(8,8);
    cx.arc(8,8,7,0.3,2*Math.PI-0.3);
    cx.closePath();
    cx.fill();
    ld.appendChild(c);
  }
}

function loop() {
  if (gameOver) {
    drawAll();
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle = '#ff0000';
    ctx.font = 'bold 22px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('GAME OVER', canvas.width/2, canvas.height/2);
    document.getElementById('msg').textContent = 'スタートボタンでリトライ';
    return;
  }
  if (won) {
    drawAll();
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle = '#ffff00';
    ctx.font = 'bold 22px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('YOU WIN!', canvas.width/2, canvas.height/2);
    document.getElementById('msg').textContent = 'クリア！スタートでもう一度';
    return;
  }
  if (!paused) {
    movePacman();
    ghosts.forEach(moveGhost);
    if (powerTimer > 0) {
      powerTimer--;
      if (powerTimer === 0) ghosts.forEach(g => g.frightened = false);
    }
    checkCollision();
  }
  drawAll();
  if (paused) {
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 20px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('PAUSE', canvas.width/2, canvas.height/2);
  }
  animFrame = requestAnimationFrame(loop);
}

document.addEventListener('keydown', e => {
  switch(e.key) {
    case 'ArrowLeft':  e.preventDefault(); inputDir={x:-1,y:0}; break;
    case 'ArrowRight': e.preventDefault(); inputDir={x:1,y:0};  break;
    case 'ArrowUp':    e.preventDefault(); inputDir={x:0,y:-1}; break;
    case 'ArrowDown':  e.preventDefault(); inputDir={x:0,y:1};  break;
    case 'p': case 'P': paused = !paused; if (!paused && !gameOver && !won) loop(); break;
  }
});

// 初期画面
ctx.fillStyle = '#000';
ctx.fillRect(0, 0, canvas.width, canvas.height);
ctx.fillStyle = '#ffff00';
ctx.font = 'bold 14px Arial';
ctx.textAlign = 'center';
ctx.fillText('スタートボタンを押してください', canvas.width/2, canvas.height/2);
</script>
</body>
</html>
"""

components.html(pacman_html, height=400, scrolling=False)

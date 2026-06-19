import streamlit as st
import streamlit.components.v1 as components

st.title("テトリス")

tetris_html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {
    background: #1a1a2e;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 10px;
    font-family: 'Courier New', monospace;
    margin: 0;
  }
  #game-container {
    display: flex;
    gap: 20px;
    align-items: flex-start;
  }
  canvas {
    border: 2px solid #e94560;
    box-shadow: 0 0 20px #e94560;
    display: block;
  }
  #side-panel {
    color: #eee;
    min-width: 120px;
  }
  #side-panel h3 {
    color: #e94560;
    margin: 0 0 8px 0;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 2px;
  }
  .info-box {
    background: #16213e;
    border: 1px solid #e94560;
    padding: 8px 12px;
    margin-bottom: 12px;
    border-radius: 4px;
  }
  .info-value {
    font-size: 22px;
    font-weight: bold;
    color: #fff;
  }
  #next-canvas {
    border: 1px solid #0f3460;
    background: #16213e;
    display: block;
  }
  #controls {
    font-size: 11px;
    color: #aaa;
    line-height: 1.8;
  }
  #controls span {
    color: #e94560;
    font-weight: bold;
  }
  #message {
    position: absolute;
    display: none;
    color: #fff;
    font-size: 18px;
    font-weight: bold;
    text-align: center;
    background: rgba(0,0,0,0.7);
    padding: 12px 20px;
    border-radius: 6px;
    border: 1px solid #e94560;
  }
  #start-btn {
    background: #e94560;
    color: #fff;
    border: none;
    padding: 8px 16px;
    font-size: 13px;
    font-family: 'Courier New', monospace;
    cursor: pointer;
    border-radius: 4px;
    width: 100%;
    margin-top: 6px;
    letter-spacing: 1px;
  }
  #start-btn:hover { background: #c73652; }
</style>
</head>
<body>
<div id="game-container">
  <div style="position:relative">
    <canvas id="board" width="240" height="480"></canvas>
    <div id="message">ゲームオーバー</div>
  </div>
  <div id="side-panel">
    <div class="info-box">
      <h3>スコア</h3>
      <div class="info-value" id="score">0</div>
    </div>
    <div class="info-box">
      <h3>レベル</h3>
      <div class="info-value" id="level">1</div>
    </div>
    <div class="info-box">
      <h3>ライン</h3>
      <div class="info-value" id="lines">0</div>
    </div>
    <div class="info-box">
      <h3>ネクスト</h3>
      <canvas id="next-canvas" width="100" height="80"></canvas>
    </div>
    <button id="start-btn" onclick="startGame()">スタート / リセット</button>
    <div class="info-box" style="margin-top:12px">
      <div id="controls">
        <span>← →</span> 移動<br>
        <span>↑</span> 回転<br>
        <span>↓</span> ソフトドロップ<br>
        <span>Space</span> ハードドロップ<br>
        <span>P</span> 一時停止
      </div>
    </div>
  </div>
</div>

<script>
const COLS = 10, ROWS = 20;
const BLOCK = 24;
const COLORS = [
  null,
  '#00f0f0', // I - シアン
  '#0000f0', // J - 青
  '#f0a000', // L - オレンジ
  '#f0f000', // O - 黄
  '#00f000', // S - 緑
  '#a000f0', // T - 紫
  '#f00000', // Z - 赤
];
const SHAPES = [
  null,
  [[0,0,0,0],[1,1,1,1],[0,0,0,0],[0,0,0,0]], // I
  [[1,0,0],[1,1,1],[0,0,0]],                  // J
  [[0,0,1],[1,1,1],[0,0,0]],                  // L
  [[1,1],[1,1]],                              // O
  [[0,1,1],[1,1,0],[0,0,0]],                  // S
  [[0,1,0],[1,1,1],[0,0,0]],                  // T
  [[1,1,0],[0,1,1],[0,0,0]],                  // Z
];

const canvas = document.getElementById('board');
const ctx = canvas.getContext('2d');
const nextCanvas = document.getElementById('next-canvas');
const nextCtx = nextCanvas.getContext('2d');

let board, piece, nextPiece, score, level, lines, gameLoop, paused, gameOver;

function createBoard() {
  return Array.from({length: ROWS}, () => Array(COLS).fill(0));
}

function randomPiece() {
  const type = Math.floor(Math.random() * 7) + 1;
  const shape = SHAPES[type].map(r => [...r]);
  return {
    type, shape,
    x: Math.floor(COLS / 2) - Math.floor(shape[0].length / 2),
    y: 0
  };
}

function startGame() {
  board = createBoard();
  score = 0; level = 1; lines = 0;
  paused = false; gameOver = false;
  document.getElementById('message').style.display = 'none';
  piece = randomPiece();
  nextPiece = randomPiece();
  updateStats();
  clearInterval(gameLoop);
  gameLoop = setInterval(tick, getSpeed());
  draw();
}

function getSpeed() {
  return Math.max(100, 500 - (level - 1) * 45);
}

function tick() {
  if (paused || gameOver) return;
  if (!movePiece(0, 1)) {
    placePiece();
    clearLines();
    piece = nextPiece;
    nextPiece = randomPiece();
    drawNext();
    if (collides(piece)) {
      gameOver = true;
      clearInterval(gameLoop);
      document.getElementById('message').style.display = 'block';
    }
  }
  draw();
}

function collides(p, ox=0, oy=0, shape=null) {
  const s = shape || p.shape;
  for (let r = 0; r < s.length; r++) {
    for (let c = 0; c < s[r].length; c++) {
      if (!s[r][c]) continue;
      const nx = p.x + c + ox;
      const ny = p.y + r + oy;
      if (nx < 0 || nx >= COLS || ny >= ROWS) return true;
      if (ny >= 0 && board[ny][nx]) return true;
    }
  }
  return false;
}

function movePiece(dx, dy) {
  if (!collides(piece, dx, dy)) {
    piece.x += dx;
    piece.y += dy;
    return true;
  }
  return false;
}

function rotatePiece() {
  const rotated = piece.shape[0].map((_, i) =>
    piece.shape.map(row => row[i]).reverse()
  );
  // Wall kick
  for (let offset of [0, -1, 1, -2, 2]) {
    if (!collides(piece, offset, 0, rotated)) {
      piece.shape = rotated;
      piece.x += offset;
      return;
    }
  }
}

function hardDrop() {
  let dy = 0;
  while (!collides(piece, 0, dy + 1)) dy++;
  piece.y += dy;
  score += dy * 2;
  placePiece();
  clearLines();
  piece = nextPiece;
  nextPiece = randomPiece();
  drawNext();
  if (collides(piece)) {
    gameOver = true;
    clearInterval(gameLoop);
    document.getElementById('message').style.display = 'block';
  }
  draw();
}

function placePiece() {
  for (let r = 0; r < piece.shape.length; r++) {
    for (let c = 0; c < piece.shape[r].length; c++) {
      if (!piece.shape[r][c]) continue;
      const ny = piece.y + r;
      const nx = piece.x + c;
      if (ny >= 0) board[ny][nx] = piece.type;
    }
  }
}

function clearLines() {
  let cleared = 0;
  for (let r = ROWS - 1; r >= 0; r--) {
    if (board[r].every(v => v)) {
      board.splice(r, 1);
      board.unshift(Array(COLS).fill(0));
      cleared++;
      r++;
    }
  }
  if (cleared) {
    const pts = [0, 100, 300, 500, 800];
    score += (pts[cleared] || 800) * level;
    lines += cleared;
    const newLevel = Math.floor(lines / 10) + 1;
    if (newLevel !== level) {
      level = newLevel;
      clearInterval(gameLoop);
      gameLoop = setInterval(tick, getSpeed());
    }
    updateStats();
  }
}

function updateStats() {
  document.getElementById('score').textContent = score;
  document.getElementById('level').textContent = level;
  document.getElementById('lines').textContent = lines;
}

function getGhostY() {
  let dy = 0;
  while (!collides(piece, 0, dy + 1)) dy++;
  return piece.y + dy;
}

function drawBlock(context, x, y, type, alpha=1) {
  const color = COLORS[type];
  context.globalAlpha = alpha;
  context.fillStyle = color;
  context.fillRect(x * BLOCK + 1, y * BLOCK + 1, BLOCK - 2, BLOCK - 2);
  // ハイライト
  context.fillStyle = 'rgba(255,255,255,0.3)';
  context.fillRect(x * BLOCK + 1, y * BLOCK + 1, BLOCK - 2, 4);
  context.fillRect(x * BLOCK + 1, y * BLOCK + 1, 4, BLOCK - 2);
  context.globalAlpha = 1;
}

function draw() {
  ctx.fillStyle = '#0d0d1a';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // グリッド線
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  ctx.lineWidth = 1;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      ctx.strokeRect(c * BLOCK, r * BLOCK, BLOCK, BLOCK);
    }
  }

  // ボード
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      if (board[r][c]) drawBlock(ctx, c, r, board[r][c]);
    }
  }

  if (piece) {
    // ゴースト
    const ghostY = getGhostY();
    for (let r = 0; r < piece.shape.length; r++) {
      for (let c = 0; c < piece.shape[r].length; c++) {
        if (piece.shape[r][c]) {
          drawBlock(ctx, piece.x + c, ghostY + r, piece.type, 0.2);
        }
      }
    }
    // 現在のピース
    for (let r = 0; r < piece.shape.length; r++) {
      for (let c = 0; c < piece.shape[r].length; c++) {
        if (piece.shape[r][c]) {
          drawBlock(ctx, piece.x + c, piece.y + r, piece.type);
        }
      }
    }
  }
}

function drawNext() {
  nextCtx.fillStyle = '#16213e';
  nextCtx.fillRect(0, 0, nextCanvas.width, nextCanvas.height);
  if (!nextPiece) return;
  const s = nextPiece.shape;
  const offsetX = Math.floor((4 - s[0].length) / 2);
  const offsetY = Math.floor((3 - s.length) / 2);
  for (let r = 0; r < s.length; r++) {
    for (let c = 0; c < s[r].length; c++) {
      if (s[r][c]) {
        const bx = (offsetX + c) * (BLOCK - 4);
        const by = (offsetY + r) * (BLOCK - 4) + 8;
        const b = BLOCK - 4;
        nextCtx.fillStyle = COLORS[nextPiece.type];
        nextCtx.fillRect(bx + 10, by + 1, b - 2, b - 2);
        nextCtx.fillStyle = 'rgba(255,255,255,0.3)';
        nextCtx.fillRect(bx + 10, by + 1, b - 2, 3);
      }
    }
  }
}

document.addEventListener('keydown', e => {
  if (!piece || gameOver) return;
  switch(e.key) {
    case 'ArrowLeft':  e.preventDefault(); if(!paused) { movePiece(-1,0); draw(); } break;
    case 'ArrowRight': e.preventDefault(); if(!paused) { movePiece(1,0);  draw(); } break;
    case 'ArrowDown':  e.preventDefault(); if(!paused) { movePiece(0,1); draw(); } break;
    case 'ArrowUp':    e.preventDefault(); if(!paused) { rotatePiece(); draw(); } break;
    case ' ':          e.preventDefault(); if(!paused) hardDrop(); break;
    case 'p': case 'P':
      paused = !paused;
      if (!paused) { clearInterval(gameLoop); gameLoop = setInterval(tick, getSpeed()); }
      break;
  }
});

// 初期画面
ctx.fillStyle = '#0d0d1a';
ctx.fillRect(0, 0, canvas.width, canvas.height);
ctx.fillStyle = '#e94560';
ctx.font = 'bold 16px Courier New';
ctx.textAlign = 'center';
ctx.fillText('スタートボタンを', COLS*BLOCK/2, ROWS*BLOCK/2 - 15);
ctx.fillText('押してください', COLS*BLOCK/2, ROWS*BLOCK/2 + 15);
</script>
</body>
</html>
"""

components.html(tetris_html, height=560, scrolling=False)

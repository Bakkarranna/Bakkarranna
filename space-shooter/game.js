/* space-shooter -- one year of contribution data, as a sky you can clear.
 *
 * Why a plain <canvas> and no framework: this repo ships no build step and no
 * JS dependencies, and the site has to open from GitHub Pages, from the repo
 * folder, or from file://. The page therefore behaves the way the SVG panels
 * do -- the palette follows prefers-color-scheme, and prefers-reduced-motion
 * removes every decorative motion (parallax drift, twinkle, screen shake)
 * without pausing the game itself.
 *
 * game.js is written as four parts, in order:
 *   1. palette, data and entity state          (this section)
 *   2. waves -- one contribution month becomes one wave
 *   3. update -- input, movement, collisions, the wave state machine
 *   4. render + HUD/overlay glue, the frame loop, and the test hook
 */
(() => {
  "use strict";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const $ = (id) => document.getElementById(id);
  const DATA = window.SHOOTER_DATA;
  const W = canvas.width;
  const H = canvas.height;

  /* ---------------------------------------------------------------- 1. state */

  // The two themes the SVG generators use, verbatim, so a block on the game
  // screen is the same colour as the same day on the heatmap. ramp[0] is the
  // "empty day" colour -- a level-0 day never spawns a block, but the quiet
  // waves drift their own filler in it.
  const PALETTES = {
    light: {
      bg: "#ffffff",
      surface: "#f6f8fa",
      rule: "#d0d7de",
      fg: "#1f2328",
      dim: "#59636e",
      ramp: ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39", "#1a7f37"],
    },
    dark: {
      bg: "#0d1117",
      surface: "#161b22",
      rule: "#30363d",
      fg: "#e6edf3",
      dim: "#8b949e",
      ramp: ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"],
    },
  };

  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const calmQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let palette = darkQuery.matches ? PALETTES.dark : PALETTES.light;
  let calm = calmQuery.matches;

  const BEST_KEY = "bakkarrarna-spaceShooter-best";
  const FIELD_PAD = 26;
  const COLS = 7; // one column per weekday, so the field is the heatmap on its side

  function readBest() {
    try {
      return Number(localStorage.getItem(BEST_KEY)) || 0;
    } catch {
      return 0; // private mode / file:// can refuse storage; never fatal
    }
  }

  function writeBest(value) {
    try {
      localStorage.setItem(BEST_KEY, String(value));
    } catch {
      /* best score is a nicety, not a requirement */
    }
  }

  const game = {
    state: "ready", // ready | playing | paused | over
    score: 0,
    best: readBest(),
    waveIndex: 0,
    wave: null,
    quiet: false,
    lap: 0,
    lives: 3,
    blocks: [],
    shots: [],
    enemyShots: [],
    powerups: [],
    particles: [],
    stars: [],
    queue: [],
    waveClock: 0,
    clearedDays: 0,
    totalDays: 0,
    shake: 0,
    flash: 0,
    player: {
      x: W / 2,
      y: H - 76,
      w: 26,
      h: 22,
      speed: 260,
      cooldown: 0,
      triple: 0,
      shield: 0,
    },
    keys: new Set(),
    pointer: null,
    banner: null,
  };

  // Stars are decor, so they are the first thing reduced motion drops.
  function seedStars() {
    const layers = [
      { n: 46, r: 0.7, v: 16, a: 0.35 },
      { n: 30, r: 1.1, v: 30, a: 0.6 },
      { n: 16, r: 1.6, v: 52, a: 0.9 },
    ];
    game.stars = layers.flatMap((layer) =>
      Array.from({ length: layer.n }, () => ({
        x: Math.random() * W,
        y: Math.random() * H,
        r: layer.r,
        v: layer.v,
        a: layer.a,
      }))
    );
  }

  // Deterministic jitter, so a rebuilt wave lays its blocks out identically and
  // a developer comparing two runs sees the same field.
  function jitter(seedText, spread) {
    let h = 2166136261;
    for (let i = 0; i < seedText.length; i += 1) {
      h ^= seedText.charCodeAt(i);
      h = (h * 16777619) >>> 0;
    }
    return (h % 1000) / 1000 * spread - spread / 2;
  }

  /* --------------------------------------------------------------- 2. waves */

  // One calendar month of contributions becomes one wave: the month's active
  // days are the blocks, coloured and armoured exactly as the heatmap shows
  // them (hp = level + 1), and the month's empty days fill the rest of the
  // formation in the "empty day" colour. A busy month is a dense, heavily
  // armoured wall; a quiet month is a thin scatter; a month with no
  // contributions at all is a formation of pure filler worth almost nothing.
  // Difficulty is the jump in size from one month to the next, so it climbs
  // with the calendar instead of by wave number.

  const MIN_BLOCKS = 8;
  const MAX_BLOCKS = 26;

  function fillBlocks(month, index, prevReal) {
    const real = (month.days || [])
      .slice()
      .sort((a, b) => b.level - a.level || b.count - a.count);
    const count = Math.min(MAX_BLOCKS, Math.max(MIN_BLOCKS, real.length + 6));
    const cols = Math.min(COLS, count);
    const rows = Math.ceil(count / cols);
    const cellW = (W - FIELD_PAD * 2) / cols;
    const cellH = 30;
    const top = 52;

    // Snake order, so a wave of three real days and nine fillers still reads
    // as a calendar block rather than three bricks in the top-left corner.
    const slots = [];
    for (let row = 0; row < rows; row += 1) {
      for (let i = 0; i < cols; i += 1) {
        slots.push({ col: row % 2 === 0 ? i : cols - 1 - i, row });
      }
    }
    slots.length = count;

    const blocks = slots.map((slot, i) => {
      const day = real[i];
      const filler = !day;
      const level = filler ? 0 : Math.max(1, Math.min(5, day.level || 1));
      const w = Math.min(30, cellW - 10);
      const h = 18;
      const x = FIELD_PAD + slot.col * cellW + (cellW - w) / 2;
      const y = top + slot.row * cellH;
      return {
        x,
        y,
        homeX: x,
        homeY: y,
        w,
        h,
        hp: level + 1,
        maxHp: level + 1,
        level,
        color: palette.ramp[level],
        points: filler ? 15 : level * 100,
        filler,
        date: day ? day.date : "",
        t: jitter(month.month + i, 6.28),
      };
    });

    const diff = (prevReal || 0) + index * 0.8 + (real.length - 10) * 0.6;
    return {
      label: month.label,
      month: month.month,
      real: real.length,
      quiet: real.length === 0,
      blocks,
      top,
      cellH,
      drop: 12 + Math.min(14, index),
      dir: 1,
      diff,
      speed: 34 + Math.min(58, diff * 2.6),
      fireCooldown: Math.max(0.55, 3.4 - diff * 0.1),
      fireClock: 1.6 + Math.random(),
      swifts: real.length > 5 ? 1 + (index % 3) : 0,
      swiftClock: 3,
    };
  }

  function buildWaves() {
    const waves = [];
    let prevReal = 0;
    DATA.waves.forEach((month, index) => {
      const wave = fillBlocks(month, index, prevReal);
      waves.push(wave);
      prevReal = wave.real;
    });
    return waves;
  }

  const WAVES = buildWaves();
  game.totalDays = WAVES.reduce((sum, wave) => sum + wave.real, 0);

  /* --------------------------------------------------------------- 3. update */

  const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
  const rand = (lo, hi) => lo + Math.random() * (hi - lo);

  function say(text) {
    const node = $("say");
    if (node) node.textContent = text;
  }

  function clearField() {
    game.blocks = [];
    game.shots = [];
    game.enemyShots = [];
    game.powerups = [];
    game.particles = [];
    game.wave = null;
  }

  /* Wave staging. Each wave gets a fresh copy of its template's blocks, so a
     lap replays the same calendar rather than a different one. */
  function startWave(index) {
    const t = WAVES[index % WAVES.length];
    const lapBoost = 1 + game.lap * 0.16;
    const wave = {
      label: t.label,
      month: t.month,
      real: t.real,
      quiet: t.quiet,
      top: t.top,
      cellH: t.cellH,
      drop: t.drop,
      dir: 1,
      diff: t.diff,
      speed: t.speed * lapBoost,
      fireCooldown: Math.max(0.4, t.fireCooldown / lapBoost),
      fireClock: 1.2 + Math.random(),
      swifts: t.swifts + game.lap,
      swiftClock: 2.4,
      blocks: t.blocks.map((b) => Object.assign({}, b)),
    };
    game.wave = wave;
    game.blocks = wave.blocks;
    game.waveIndex = index;
    game.waveClock = 0;
    game.shots = [];
    game.enemyShots = [];
    game.powerups = [];
    game.banner = {
      title: `wave ${index + 1} / ${WAVES.length} &mdash; ${t.label}`,
      sub: t.quiet
        ? "no contributions that month &mdash; nothing here is worth points"
        : `${t.real} contribution day${t.real === 1 ? "" : "s"}, ${t.total} commits`,
      t: 2.6,
    };
    say(`Wave ${index + 1} of ${WAVES.length}, ${t.label}.`);
  }

  function startGame() {
    game.state = "playing";
    game.score = 0;
    game.lives = 3;
    game.waveIndex = 0;
    game.lap = 0;
    game.clearedDays = 0;
    game.player.x = W / 2;
    game.player.y = H - 76;
    game.player.triple = 0;
    game.player.shield = 0;
    game.player.cooldown = 0;
    game.particles = [];
    clearField();
    startWave(0);
    syncHud();
  }

  /* A wave ends clear, breached or lost -- all three land here. */
  function finishWave(cleared) {
    game.waveClock = 0;
    if (!cleared) return;
    const wave = game.wave;
    const bonus = wave.real * 200 + game.lives * 250;
    game.score += bonus;
    game.banner = {
      title: `wave cleared &mdash; ${wave.label}`,
      sub: wave.quiet ? "nothing to bank, but nothing lost either" : `+${bonus} bonus`,
      t: 2.4,
    };
    if (game.waveIndex + 1 >= WAVES.length) {
      game.lap += 1;
      game.banner = {
        title: `the year is clear &mdash; lap ${game.lap + 1}`,
        sub: `+${bonus} bonus &middot; every wave comes back faster`,
        t: 3,
      };
    }
    say(`${wave.label} cleared.`);
    syncHud();
  }

  function loseLife(reason) {
    if (game.state !== "playing") return;
    game.lives -= 1;
    game.shake = calm ? 0 : 14;
    game.flash = 0.35;
    game.player.triple = 0;
    game.player.shield = 0;
    game.enemyShots = [];
    game.player.x = W / 2;
    if (game.lives <= 0) {
      game.state = "over";
      game.banner = null;
      if (game.score > game.best) {
        game.best = game.score;
        writeBest(game.best);
      }
      say(`Game over. Score ${game.score}.`);
    } else {
      say(`${reason}. ${game.lives} lives left.`);
    }
    syncHud();
  }

  /* Any two axis-aligned rects. Blocks, shots and pickups all use x/y/w/h,
     so one overlap test covers every pair in the game. */
  function overlaps(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function burst(x, y, color, n) {
    if (calm) n = Math.min(n, 4);
    for (let i = 0; i < n; i += 1) {
      const a = rand(0, 6.283);
      const sp = rand(40, 190);
      game.particles.push({
        x,
        y,
        vx: Math.cos(a) * sp,
        vy: Math.sin(a) * sp,
        life: rand(0.25, 0.7),
        t: 0,
        color,
      });
    }
  }

  /* Pickups are deliberately rare and short-lived: one at a time, drifting
     down, so a player has to leave cover to collect it. */
  const POWERUP_KINDS = [
    { kind: "triple", color: "#39d353", label: "triple" },
    { kind: "shield", color: "#58a6ff", label: "shield" },
    { kind: "life", color: "#f778ba", label: "1up" },
  ];

  function dropPowerup(x, y, chance) {
    if (Math.random() > chance) return;
    const pick = POWERUP_KINDS[Math.floor(Math.random() * (game.lives < 3 ? 3 : 2))];
    game.powerups.push({ x: x - 9, y: y - 9, w: 18, h: 18, vy: 62, ...pick });
  }

  function killBlock(block) {
    game.score += block.points;
    game.clearedDays += block.filler ? 0 : 1;
    burst(block.x + block.w / 2, block.y + block.h / 2, block.color, calm ? 4 : 12);
    // Real days (heavier blocks) are the ones that pay out pickups; a month
    // of filler never rewards chasing it.
    dropPowerup(block.x + block.w / 2, block.y, block.filler ? 0.02 : 0.12);
    game.blocks.splice(game.blocks.indexOf(block), 1);
    if (game.blocks.length === 0) finishWave(true);
    syncHud();
  }

  function firePlayer() {
    const p = game.player;
    if (p.cooldown > 0) return;
    p.cooldown = p.triple > 0 ? 0.24 : 0.3;
    const muzzle = p.y - p.h / 2;
    const push = (vx) => game.shots.push({ x: p.x - 1.5, y: muzzle, w: 3, h: 12, vx, vy: -430 });
    if (p.triple > 0) {
      push(-130);
      push(0);
      push(130);
    } else {
      push(0);
    }
  }

  function updatePlayer(dt) {
    const p = game.player;
    const keys = game.keys;
    let dx = 0;
    if (keys.has("ArrowLeft") || keys.has("KeyA")) dx -= 1;
    if (keys.has("ArrowRight") || keys.has("KeyD")) dx += 1;
    p.x = clamp(p.x + dx * p.speed * dt, p.w, W - p.w);

    // The pointer wins over the keyboard while it is actually being dragged:
    // one consistent "wherever the finger is" rule beats blending the two.
    if (game.pointer && dx === 0) {
      const target = clamp(game.pointer.x, p.w, W - p.w);
      p.x += (target - p.x) * Math.min(1, dt * 16);
    }

    p.cooldown = Math.max(0, p.cooldown - dt);
    p.triple = Math.max(0, p.triple - dt);
    p.shield = Math.max(0, p.shield - dt);
    if (keys.has("Space") || keys.has("KeyZ")) firePlayer();
  }

  /* The formation breathes sideways and steps down at the edges, the way the
     heatmap reads left-to-right: one slow pass per wave, no jam into the
     player. Reaching the player's line costs a life. */
  function updateBlocks(dt) {
    const wave = game.wave;
    if (!wave || game.blocks.length === 0) return;
    if (wave.driftX === undefined) {
      wave.driftX = 0;
      wave.driftY = 0;
      wave.edge = 1;
    }
    const sway = Math.sin(game.waveClock * 0.6 + wave.diff * 0.2) * 9;
    wave.driftX += wave.edge * wave.speed * dt;
    if (wave.driftX > 44) {
      wave.driftX = 44;
      wave.edge = -1;
      wave.driftY = Math.min(26, wave.driftY + 7);
    } else if (wave.driftX < -44) {
      wave.driftX = -44;
      wave.edge = 1;
      wave.driftY = Math.min(26, wave.driftY + 7);
    }
    for (const b of game.blocks) {
      b.x = b.homeX + sway + wave.driftX;
      b.y = b.homeY + wave.driftY;
    }
    const breach = H - 118;
    for (const b of game.blocks) {
      if (b.y + b.h >= breach && (wave.breached === undefined || !wave.breached)) {
        wave.breached = true;
        burst(clamp(b.x, b.w / 2, W - b.w / 2), breach, b.color, calm ? 6 : 20);
        loseLife(`the ${wave.label} wave reached your line`);
        return;
      }
    }
  }

})();

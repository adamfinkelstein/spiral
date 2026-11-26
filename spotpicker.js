// Clickable detail spots over the low-res input, shared by card.html (0a ->
// 5a) and procedure.html (step 0). The spots come from card/spots.js (SPOTS,
// SPOT_SELECTED; written by build_card.py). Markup:
//   <div class="pick" data-zoom="IMG_ID" data-prefix="card/img/a_zoom_"
//        data-info="TEXT_ID" data-wrong="1"><img src="card/img/a_input.png"></div>
// Clicking box k shows PREFIX + kk + ".png" in the image IMG_ID; data-info
// names an element for "Spot k: turn, radius" (data-wrong adds the
// wrong-groove count, which only card.html's path figure shows).

(function () {
  var style = document.createElement("style");
  style.textContent =
    ".pick { position: relative; line-height: 0; }" +
    ".pick img { border: none; width: 100%; }" +
    ".spot { position: absolute; box-sizing: border-box; border: 2px solid transparent; cursor: pointer; }" +
    ".spot:hover { border-color: rgba(255,255,255,0.6); }" +
    ".spot.on { border-color: #fff; }";
  document.head.appendChild(style);

  function two(k) { return (k < 10 ? "0" : "") + k; }

  document.querySelectorAll(".pick").forEach(function (pick) {
    var zoom = document.getElementById(pick.dataset.zoom);
    var info = pick.dataset.info && document.getElementById(pick.dataset.info);
    var boxes = SPOTS.map(function (s, k) {
      var box = document.createElement("div");
      box.className = "spot";
      box.title = "spot " + (k + 1);
      box.style.left = 100 * s.left + "%";
      box.style.top = 100 * s.top + "%";
      box.style.width = box.style.height = 100 * s.size + "%";
      box.addEventListener("click", function () { show(k); });
      pick.appendChild(box);
      return box;
    });
    function show(k) {
      var s = SPOTS[k];
      zoom.src = pick.dataset.prefix + two(k) + ".png";
      boxes.forEach(function (box, j) { box.classList.toggle("on", j === k); });
      if (!info) return;
      var text = "Spot " + (k + 1) + " of " + SPOTS.length + ": turn " + s.turn + ", radius " + s.radius + " px";
      if (pick.dataset.wrong) {
        text += s.wrong ? "; " + s.wrong + " path columns here on the wrong groove." : "; no wrong-groove columns here.";
      }
      info.textContent = text;
    }
    show(SPOT_SELECTED);
  });
})();

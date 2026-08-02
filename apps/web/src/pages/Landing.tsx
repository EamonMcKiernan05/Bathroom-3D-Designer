import { Link } from 'react-router-dom';

export function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-sky-50 to-white px-6">
      <div className="max-w-2xl text-center">
        <div className="mb-4 text-6xl">🛁</div>
        <h1 className="text-4xl font-bold tracking-tight text-neutral-900">Bathroom 3D Designer</h1>
        <p className="mt-4 text-lg text-neutral-600">
          Design your bathroom in your browser. Draw the room, add real products, tile the walls and floor,
          and export a shopping list — all in real-time 3D.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Link
            to="/editor"
            className="rounded-xl bg-sky-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-200 transition hover:bg-sky-700"
          >
            Start designing →
          </Link>
          <Link
            to="/designs"
            className="rounded-xl border border-neutral-300 bg-white px-6 py-3 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-50"
          >
            My designs
          </Link>
        </div>
        <div className="mt-12 grid grid-cols-3 gap-4 text-left">
          {[
            ['📐', 'Draw your room', 'Click-to-draw walls for rectangular or L-shaped rooms, add doors and windows.'],
            ['🧱', 'Tile it for real', 'Real-world tile sizes, straight or diagonal layouts, grout settings.'],
            ['🛒', 'Export the list', 'Bill of materials with retailer links, CSV download, 2D floorplan export.'],
          ].map(([icon, title, body]) => (
            <div key={title} className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
              <div className="text-2xl">{icon}</div>
              <h3 className="mt-2 text-sm font-semibold text-neutral-900">{title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-neutral-500">{body}</p>
            </div>
          ))}
        </div>
        <p className="mt-10 text-[11px] text-neutral-400">
          Demo build — product catalogue and textures are placeholder data until web scraping is wired in.
          All dimensions in millimetres. Runs fully in your browser.
        </p>
      </div>
    </div>
  );
}

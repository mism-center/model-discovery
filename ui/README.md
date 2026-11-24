# MISM Discovery Portal UI

The frontend for the Multiscale Immune Systems Modeling (MISM) discovery portal, providing a search/upload interface for multiscale models.

## Tech Stack

- **Framework**: [React Router 7](https://reactrouter.com/) with server-side rendering
- **React**: v19
- **TypeScript**: v5.9
- **Styling**: [TailwindCSS v4](https://tailwindcss.com/) with a custom theme plugin
- **Component Library**: [HeroUI v2.8](https://www.heroui.com/)
- **Build Tool**: [Vite v7](https://vite.dev/)

## Getting Started

### Prerequisites

- Node.js (LTS recommended)
- npm

### Installation

```bash
npm install
```

### Development

Start the development server with HMR:

```bash
npm run dev
```

The application will be available at `http://localhost:5173`.

### Available Scripts

| Command             | Description                        |
| ------------------- | ---------------------------------- |
| `npm run dev`       | Start dev server with HMR          |
| `npm run build`     | Create a production build          |
| `npm start`         | Run the production server          |
| `npm run typecheck` | Generate route types and run `tsc` |
| `npm run lint`      | Run ESLint                         |
| `npm run lint:fix`  | Run ESLint with auto-fix           |
| `npm run format`    | Format code with Prettier          |

## Project Structure

```
app/
├── api/               # API hooks and service clients
├── components/
│   ├── layout/        # Global layout components
│   └── sections/
│       └── search/    # Search UI
├── contexts/          # React context providers
├── routes/            # File-based route components
├── styles/            # TailwindCSS config and custom plugins
├── root.tsx           # Root layout, providers, and error boundary
└── routes.ts          # Route definitions
```

## Building for Production

```bash
npm run build
```

The build outputs to `build/`:

```
build/
├── client/    # Static assets
└── server/    # Server-side rendering code
```

Start the production server:

```bash
npm start
```

# Brainy Storm Frontend

This is the React + TypeScript frontend for Brainy Storm, a brainstorming workspace designed to help teams capture, organize, and vote on ideas during live conversations.

## Overview

The interface presents a collaborative idea board with:

- a session sidebar for brainstorming spaces
- searchable recent sessions
- a live board for idea cards and voting
- a recording/transcript dock for conversational context
- saved ideas and lightweight session management

The current UI is a polished concept prototype for the product experience and is built as a Vite app.

## Tech Stack

- React 19
- TypeScript
- Vite
- Lucide React icons
- Custom CSS styling

## Project Structure

```text
frontend/
├── src/
│   ├── App.tsx
│   ├── App.css
│   ├── main.tsx
│   └── index.css
├── public/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── README.md
└── index.html
```

## Getting Started

From the repository root:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Then open:

```text
http://localhost:5173
```

## Available Scripts

```bash
npm run dev      # start the Vite dev server
npm run build    # type-check and build the app for production
npm run preview  # preview the production build locally
npm run lint     # run the project's linter
```

## Notes

- The app is currently frontend-only and uses seeded mock data for brainstorming sessions and ideas.
- The `npm run dev` command is intended to be used while developing locally.
- If the app is being served from another environment or a remote host, update the port/host settings as needed.

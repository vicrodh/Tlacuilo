# Tlacuilo Pages

Sitio estatico de Tlacuilo (React + Vite + TypeScript), desplegado con GitHub Pages via Actions.

## Desarrollo

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Despliegue (GitHub Pages)

- Source: GitHub Actions
- El workflow publica el contenido de `dist`.
- No es necesario versionar `dist` ni `CNAME`.

## DNS (Cloudflare)

Crear un registro CNAME:

- Nombre: `tlacuilo`
- Target: `vicrodh.github.io`

Luego, verificar el dominio en Settings -> Pages del repositorio.

/**
 * Internationalization (i18n) support for Tlacuilo.
 * Translations are organized by language code and nested by feature/section.
 */

import type { Language } from '$lib/stores/settings.svelte';

export interface Translations {
  // Navigation
  nav: {
    home: string;
    recentFiles: string;
    allTools: string;
    settings: string;
    favorites: string;
  };

  // Common actions
  actions: {
    open: string;
    save: string;
    cancel: string;
    clear: string;
    close: string;
    add: string;
    remove: string;
    delete: string;
    merge: string;
    split: string;
    rotate: string;
    convert: string;
    compress: string;
    export: string;
  };

  // Tools
  tools: {
    viewer: string;
    viewerDesc: string;
    mergePdf: string;
    mergePdfDesc: string;
    splitPdf: string;
    splitPdfDesc: string;
    rotatePdf: string;
    rotatePdfDesc: string;
    compressPdf: string;
    compressPdfDesc: string;
    ocr: string;
    ocrDesc: string;
    imagesToPdf: string;
    pdfToImages: string;
    docsToPdf: string;
    pdfToDocs: string;
  };

  // Settings
  settings: {
    title: string;
    language: string;
    languageDesc: string;
    quickTools: string;
    quickToolsDesc: string;
    showInFavorites: string;
    recentFiles: string;
    recentFilesDesc: string;
    showInHome: string;
    clearRecentFiles: string;
    filesInHistory: string;
    storage: string;
    storageDesc: string;
    clearCache: string;
    clearCacheDesc: string;
  };

  // Viewer
  viewer: {
    title: string;
    openPdf: string;
    description: string;
    page: string;
    of: string;
    zoom: string;
    tools: {
      select: string;
      pan: string;
      pen: string;
      highlight: string;
      text: string;
      redact: string;
      stamp: string;
    };
  };

  // Dashboard
  dashboard: {
    quickTools: string;
    recentFiles: string;
    noRecentFiles: string;
    today: string;
    yesterday: string;
    daysAgo: string;
  };

  // Status
  status: {
    ready: string;
    loading: string;
    processing: string;
    complete: string;
    error: string;
    noFileSelected: string;
    filesOpen: string;
  };
}

const en: Translations = {
  nav: {
    home: 'Home',
    recentFiles: 'Recent Files',
    allTools: 'All Tools',
    settings: 'Settings',
    favorites: 'Favorites',
  },
  actions: {
    open: 'Open',
    save: 'Save',
    cancel: 'Cancel',
    clear: 'Clear',
    close: 'Close',
    add: 'Add',
    remove: 'Remove',
    delete: 'Delete',
    merge: 'Merge',
    split: 'Split',
    rotate: 'Rotate',
    convert: 'Convert',
    compress: 'Compress',
    export: 'Export',
  },
  tools: {
    viewer: 'Viewer',
    viewerDesc: 'View, annotate, and edit PDFs',
    mergePdf: 'Merge PDF',
    mergePdfDesc: 'Combine multiple PDFs into one',
    splitPdf: 'Split PDF',
    splitPdfDesc: 'Extract or separate pages',
    rotatePdf: 'Rotate PDF',
    rotatePdfDesc: 'Rotate pages in a PDF',
    compressPdf: 'Compress PDF',
    compressPdfDesc: 'Reduce PDF file size',
    ocr: 'OCR',
    ocrDesc: 'Extract text from scanned PDFs',
    imagesToPdf: 'Images to PDF',
    pdfToImages: 'PDF to Images',
    docsToPdf: 'Documents to PDF',
    pdfToDocs: 'PDF to Documents',
  },
  settings: {
    title: 'Settings',
    language: 'Language',
    languageDesc: 'Choose your preferred language for the interface.',
    quickTools: 'Quick Tools',
    quickToolsDesc: 'Choose which tools appear in the sidebar favorites section.',
    showInFavorites: 'Show in Favorites',
    recentFiles: 'Recent Files',
    recentFilesDesc: 'Manage how recent files are displayed and stored.',
    showInHome: 'Show Recent Files in Home',
    clearRecentFiles: 'Clear Recent Files',
    filesInHistory: 'files in history',
    storage: 'Storage',
    storageDesc: 'Manage cached data and temporary files.',
    clearCache: 'Clear Cache',
    clearCacheDesc: 'Remove cached thumbnails and temporary data',
  },
  viewer: {
    title: 'PDF Viewer',
    openPdf: 'Open PDF',
    description: 'Open a PDF to view, annotate, and edit. Use the tools in the toolbar to highlight, draw, add text, and more.',
    page: 'Page',
    of: 'of',
    zoom: 'Zoom',
    tools: {
      select: 'Select',
      pan: 'Pan',
      pen: 'Pen',
      highlight: 'Highlight',
      text: 'Text',
      redact: 'Redact',
      stamp: 'Stamp',
    },
  },
  dashboard: {
    quickTools: 'Quick Tools',
    recentFiles: 'Recent Files',
    noRecentFiles: 'No recent files',
    today: 'Today',
    yesterday: 'Yesterday',
    daysAgo: 'days ago',
  },
  status: {
    ready: 'Ready',
    loading: 'Loading...',
    processing: 'Processing...',
    complete: 'Complete',
    error: 'Error',
    noFileSelected: 'No file selected',
    filesOpen: 'files open',
  },
};

const es: Translations = {
  nav: {
    home: 'Inicio',
    recentFiles: 'Archivos Recientes',
    allTools: 'Herramientas',
    settings: 'Configuracion',
    favorites: 'Favoritos',
  },
  actions: {
    open: 'Abrir',
    save: 'Guardar',
    cancel: 'Cancelar',
    clear: 'Limpiar',
    close: 'Cerrar',
    add: 'Agregar',
    remove: 'Quitar',
    delete: 'Eliminar',
    merge: 'Combinar',
    split: 'Dividir',
    rotate: 'Rotar',
    convert: 'Convertir',
    compress: 'Comprimir',
    export: 'Exportar',
  },
  tools: {
    viewer: 'Visor',
    viewerDesc: 'Ver, anotar y editar PDFs',
    mergePdf: 'Combinar PDF',
    mergePdfDesc: 'Unir varios PDFs en uno',
    splitPdf: 'Dividir PDF',
    splitPdfDesc: 'Extraer o separar paginas',
    rotatePdf: 'Rotar PDF',
    rotatePdfDesc: 'Rotar paginas de un PDF',
    compressPdf: 'Comprimir PDF',
    compressPdfDesc: 'Reducir tamano del archivo',
    ocr: 'OCR',
    ocrDesc: 'Extraer texto de PDFs escaneados',
    imagesToPdf: 'Imagenes a PDF',
    pdfToImages: 'PDF a Imagenes',
    docsToPdf: 'Documentos a PDF',
    pdfToDocs: 'PDF a Documentos',
  },
  settings: {
    title: 'Configuracion',
    language: 'Idioma',
    languageDesc: 'Elige tu idioma preferido para la interfaz.',
    quickTools: 'Herramientas Rapidas',
    quickToolsDesc: 'Elige que herramientas aparecen en la seccion de favoritos.',
    showInFavorites: 'Mostrar en Favoritos',
    recentFiles: 'Archivos Recientes',
    recentFilesDesc: 'Administra como se muestran y almacenan los archivos recientes.',
    showInHome: 'Mostrar Archivos Recientes en Inicio',
    clearRecentFiles: 'Limpiar Archivos Recientes',
    filesInHistory: 'archivos en historial',
    storage: 'Almacenamiento',
    storageDesc: 'Administra datos en cache y archivos temporales.',
    clearCache: 'Limpiar Cache',
    clearCacheDesc: 'Eliminar miniaturas y datos temporales',
  },
  viewer: {
    title: 'Visor de PDF',
    openPdf: 'Abrir PDF',
    description: 'Abre un PDF para ver, anotar y editar. Usa las herramientas para resaltar, dibujar, agregar texto y mas.',
    page: 'Pagina',
    of: 'de',
    zoom: 'Zoom',
    tools: {
      select: 'Seleccionar',
      pan: 'Desplazar',
      pen: 'Lapiz',
      highlight: 'Resaltar',
      text: 'Texto',
      redact: 'Redactar',
      stamp: 'Sello',
    },
  },
  dashboard: {
    quickTools: 'Herramientas Rapidas',
    recentFiles: 'Archivos Recientes',
    noRecentFiles: 'Sin archivos recientes',
    today: 'Hoy',
    yesterday: 'Ayer',
    daysAgo: 'dias atras',
  },
  status: {
    ready: 'Listo',
    loading: 'Cargando...',
    processing: 'Procesando...',
    complete: 'Completado',
    error: 'Error',
    noFileSelected: 'Sin archivo seleccionado',
    filesOpen: 'archivos abiertos',
  },
};

const pt: Translations = {
  nav: {
    home: 'Inicio',
    recentFiles: 'Arquivos Recentes',
    allTools: 'Ferramentas',
    settings: 'Configuracoes',
    favorites: 'Favoritos',
  },
  actions: {
    open: 'Abrir',
    save: 'Salvar',
    cancel: 'Cancelar',
    clear: 'Limpar',
    close: 'Fechar',
    add: 'Adicionar',
    remove: 'Remover',
    delete: 'Excluir',
    merge: 'Mesclar',
    split: 'Dividir',
    rotate: 'Girar',
    convert: 'Converter',
    compress: 'Comprimir',
    export: 'Exportar',
  },
  tools: {
    viewer: 'Visualizador',
    viewerDesc: 'Ver, anotar e editar PDFs',
    mergePdf: 'Mesclar PDF',
    mergePdfDesc: 'Combinar varios PDFs em um',
    splitPdf: 'Dividir PDF',
    splitPdfDesc: 'Extrair ou separar paginas',
    rotatePdf: 'Girar PDF',
    rotatePdfDesc: 'Girar paginas de um PDF',
    compressPdf: 'Comprimir PDF',
    compressPdfDesc: 'Reduzir tamanho do arquivo',
    ocr: 'OCR',
    ocrDesc: 'Extrair texto de PDFs digitalizados',
    imagesToPdf: 'Imagens para PDF',
    pdfToImages: 'PDF para Imagens',
    docsToPdf: 'Documentos para PDF',
    pdfToDocs: 'PDF para Documentos',
  },
  settings: {
    title: 'Configuracoes',
    language: 'Idioma',
    languageDesc: 'Escolha seu idioma preferido para a interface.',
    quickTools: 'Ferramentas Rapidas',
    quickToolsDesc: 'Escolha quais ferramentas aparecem na secao de favoritos.',
    showInFavorites: 'Mostrar nos Favoritos',
    recentFiles: 'Arquivos Recentes',
    recentFilesDesc: 'Gerencie como os arquivos recentes sao exibidos e armazenados.',
    showInHome: 'Mostrar Arquivos Recentes na Pagina Inicial',
    clearRecentFiles: 'Limpar Arquivos Recentes',
    filesInHistory: 'arquivos no historico',
    storage: 'Armazenamento',
    storageDesc: 'Gerencie dados em cache e arquivos temporarios.',
    clearCache: 'Limpar Cache',
    clearCacheDesc: 'Remover miniaturas e dados temporarios',
  },
  viewer: {
    title: 'Visualizador de PDF',
    openPdf: 'Abrir PDF',
    description: 'Abra um PDF para ver, anotar e editar. Use as ferramentas para destacar, desenhar, adicionar texto e mais.',
    page: 'Pagina',
    of: 'de',
    zoom: 'Zoom',
    tools: {
      select: 'Selecionar',
      pan: 'Mover',
      pen: 'Caneta',
      highlight: 'Destacar',
      text: 'Texto',
      redact: 'Censurar',
      stamp: 'Carimbo',
    },
  },
  dashboard: {
    quickTools: 'Ferramentas Rapidas',
    recentFiles: 'Arquivos Recentes',
    noRecentFiles: 'Sem arquivos recentes',
    today: 'Hoje',
    yesterday: 'Ontem',
    daysAgo: 'dias atras',
  },
  status: {
    ready: 'Pronto',
    loading: 'Carregando...',
    processing: 'Processando...',
    complete: 'Concluido',
    error: 'Erro',
    noFileSelected: 'Nenhum arquivo selecionado',
    filesOpen: 'arquivos abertos',
  },
};

const fr: Translations = {
  nav: {
    home: 'Accueil',
    recentFiles: 'Fichiers Recents',
    allTools: 'Outils',
    settings: 'Parametres',
    favorites: 'Favoris',
  },
  actions: {
    open: 'Ouvrir',
    save: 'Enregistrer',
    cancel: 'Annuler',
    clear: 'Effacer',
    close: 'Fermer',
    add: 'Ajouter',
    remove: 'Supprimer',
    delete: 'Effacer',
    merge: 'Fusionner',
    split: 'Diviser',
    rotate: 'Pivoter',
    convert: 'Convertir',
    compress: 'Compresser',
    export: 'Exporter',
  },
  tools: {
    viewer: 'Visionneuse',
    viewerDesc: 'Voir, annoter et modifier des PDFs',
    mergePdf: 'Fusionner PDF',
    mergePdfDesc: 'Combiner plusieurs PDFs en un',
    splitPdf: 'Diviser PDF',
    splitPdfDesc: 'Extraire ou separer des pages',
    rotatePdf: 'Pivoter PDF',
    rotatePdfDesc: 'Pivoter les pages d\'un PDF',
    compressPdf: 'Compresser PDF',
    compressPdfDesc: 'Reduire la taille du fichier',
    ocr: 'OCR',
    ocrDesc: 'Extraire le texte des PDFs scannes',
    imagesToPdf: 'Images vers PDF',
    pdfToImages: 'PDF vers Images',
    docsToPdf: 'Documents vers PDF',
    pdfToDocs: 'PDF vers Documents',
  },
  settings: {
    title: 'Parametres',
    language: 'Langue',
    languageDesc: 'Choisissez votre langue preferee pour l\'interface.',
    quickTools: 'Outils Rapides',
    quickToolsDesc: 'Choisissez les outils qui apparaissent dans la section favoris.',
    showInFavorites: 'Afficher dans les Favoris',
    recentFiles: 'Fichiers Recents',
    recentFilesDesc: 'Gerez l\'affichage et le stockage des fichiers recents.',
    showInHome: 'Afficher les Fichiers Recents sur l\'Accueil',
    clearRecentFiles: 'Effacer les Fichiers Recents',
    filesInHistory: 'fichiers dans l\'historique',
    storage: 'Stockage',
    storageDesc: 'Gerez les donnees en cache et les fichiers temporaires.',
    clearCache: 'Vider le Cache',
    clearCacheDesc: 'Supprimer les miniatures et donnees temporaires',
  },
  viewer: {
    title: 'Visionneuse PDF',
    openPdf: 'Ouvrir PDF',
    description: 'Ouvrez un PDF pour le voir, l\'annoter et le modifier. Utilisez les outils pour surligner, dessiner, ajouter du texte et plus.',
    page: 'Page',
    of: 'sur',
    zoom: 'Zoom',
    tools: {
      select: 'Selectionner',
      pan: 'Deplacer',
      pen: 'Stylo',
      highlight: 'Surligner',
      text: 'Texte',
      redact: 'Caviarder',
      stamp: 'Tampon',
    },
  },
  dashboard: {
    quickTools: 'Outils Rapides',
    recentFiles: 'Fichiers Recents',
    noRecentFiles: 'Aucun fichier recent',
    today: 'Aujourd\'hui',
    yesterday: 'Hier',
    daysAgo: 'jours',
  },
  status: {
    ready: 'Pret',
    loading: 'Chargement...',
    processing: 'Traitement...',
    complete: 'Termine',
    error: 'Erreur',
    noFileSelected: 'Aucun fichier selectionne',
    filesOpen: 'fichiers ouverts',
  },
};

const de: Translations = {
  nav: {
    home: 'Startseite',
    recentFiles: 'Zuletzt verwendet',
    allTools: 'Werkzeuge',
    settings: 'Einstellungen',
    favorites: 'Favoriten',
  },
  actions: {
    open: 'Offnen',
    save: 'Speichern',
    cancel: 'Abbrechen',
    clear: 'Loschen',
    close: 'Schliessen',
    add: 'Hinzufugen',
    remove: 'Entfernen',
    delete: 'Loschen',
    merge: 'Zusammenfuhren',
    split: 'Teilen',
    rotate: 'Drehen',
    convert: 'Konvertieren',
    compress: 'Komprimieren',
    export: 'Exportieren',
  },
  tools: {
    viewer: 'Betrachter',
    viewerDesc: 'PDFs anzeigen, annotieren und bearbeiten',
    mergePdf: 'PDF zusammenfuhren',
    mergePdfDesc: 'Mehrere PDFs zu einem kombinieren',
    splitPdf: 'PDF teilen',
    splitPdfDesc: 'Seiten extrahieren oder trennen',
    rotatePdf: 'PDF drehen',
    rotatePdfDesc: 'Seiten eines PDFs drehen',
    compressPdf: 'PDF komprimieren',
    compressPdfDesc: 'Dateigrösse reduzieren',
    ocr: 'OCR',
    ocrDesc: 'Text aus gescannten PDFs extrahieren',
    imagesToPdf: 'Bilder zu PDF',
    pdfToImages: 'PDF zu Bildern',
    docsToPdf: 'Dokumente zu PDF',
    pdfToDocs: 'PDF zu Dokumenten',
  },
  settings: {
    title: 'Einstellungen',
    language: 'Sprache',
    languageDesc: 'Wahlen Sie Ihre bevorzugte Sprache fur die Oberflache.',
    quickTools: 'Schnellwerkzeuge',
    quickToolsDesc: 'Wahlen Sie, welche Werkzeuge im Favoritenbereich erscheinen.',
    showInFavorites: 'In Favoriten anzeigen',
    recentFiles: 'Zuletzt verwendet',
    recentFilesDesc: 'Verwalten Sie die Anzeige und Speicherung der zuletzt verwendeten Dateien.',
    showInHome: 'Zuletzt verwendete Dateien auf der Startseite anzeigen',
    clearRecentFiles: 'Verlauf loschen',
    filesInHistory: 'Dateien im Verlauf',
    storage: 'Speicher',
    storageDesc: 'Zwischengespeicherte Daten und temporare Dateien verwalten.',
    clearCache: 'Cache leeren',
    clearCacheDesc: 'Miniaturbilder und temporare Daten entfernen',
  },
  viewer: {
    title: 'PDF-Betrachter',
    openPdf: 'PDF offnen',
    description: 'Offnen Sie ein PDF zum Anzeigen, Annotieren und Bearbeiten. Verwenden Sie die Werkzeuge zum Hervorheben, Zeichnen, Text hinzufugen und mehr.',
    page: 'Seite',
    of: 'von',
    zoom: 'Zoom',
    tools: {
      select: 'Auswahlen',
      pan: 'Verschieben',
      pen: 'Stift',
      highlight: 'Hervorheben',
      text: 'Text',
      redact: 'Schwarzen',
      stamp: 'Stempel',
    },
  },
  dashboard: {
    quickTools: 'Schnellwerkzeuge',
    recentFiles: 'Zuletzt verwendet',
    noRecentFiles: 'Keine aktuellen Dateien',
    today: 'Heute',
    yesterday: 'Gestern',
    daysAgo: 'Tage',
  },
  status: {
    ready: 'Bereit',
    loading: 'Laden...',
    processing: 'Verarbeiten...',
    complete: 'Abgeschlossen',
    error: 'Fehler',
    noFileSelected: 'Keine Datei ausgewahlt',
    filesOpen: 'Dateien geoeffnet',
  },
};

// All translations
const translations: Record<Language, Translations> = {
  en,
  es,
  pt,
  fr,
  de,
};

export default translations;

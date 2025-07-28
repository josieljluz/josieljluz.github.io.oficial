import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Equivalente ao __dirname em ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Função para formatar data no padrão brasileiro com fuso de Fortaleza
function formatDateToBrazilian(isoDate) {
  const date = new Date(isoDate);
  return new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'America/Fortaleza',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date).replace(',', '');
}

// Função para converter bytes em formato legível (KB, MB, etc.)
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Configurações do projeto
const config = {
  outputFile: 'files_metadata.json',
  excludedFiles: [
    'index.html', 'style.css', 'script.js', '.gitlab-ci.yaml',
    'files_metadata.json', 'generate_metadata.js', 'package.json',
    'package-lock.json', '.gitlab-ci.yml', '.gitignore', 'Gemfile',
    '_config.yml', 'README.md', 'playlists.py', 'playlists2.py',
    'Playlist.py', 'playlists.m3u.py', 'TiviMate.py', 'requirements.txt',
    'playlists.log', 'Gemfile.lock'
  ],
  githubUser: 'josieljluz',
  githubRepo: 'josieljluz.github.io.oficial',
  branch: process.env.CI_COMMIT_REF_NAME || 'main',
  readableSize: true // Se true, exibe tamanhos legíveis como "MB", senão exibe em bytes
};

// Função para obter a lista de arquivos e gerar metadados
function getLocalFiles() {
  const allFiles = fs.readdirSync('.', { withFileTypes: true });

  return allFiles
    .filter(dirent => dirent.isFile())
    .map(dirent => dirent.name)
    .filter(file => !config.excludedFiles.includes(file))
    .map(file => {
      const stats = fs.statSync(file);
      return {
        name: file,
        path: file,
        tamanho: config.readableSize ? formatFileSize(stats.size) : `${stats.size} Bytes`,
        ...(config.readableSize ? {} : { sizeInBytes: stats.size }),
        size: fs.statSync(file).size,
        ultimaModificacao: formatDateToBrazilian(stats.mtime),
        lastModified: stats.mtime.toISOString(),
        download_url: `https://raw.githubusercontent.com/${config.githubUser}/${config.githubRepo}/${config.branch}/${file}`,
        file_type: path.extname(file).toLowerCase().replace('.', '') || 'file'
      };
    });
}

// Função principal para gerar o metadata
function generateMetadata() {
  try {
    console.log('⏳ Iniciando geração de metadados...');

    const filesMetadata = getLocalFiles();

    fs.writeFileSync(
      path.join(__dirname, config.outputFile),
      JSON.stringify(filesMetadata, null, 2)
    );

    console.log(`✅ Metadados gerados com sucesso em ${config.outputFile}`);
    console.log(`📊 Total de arquivos processados: ${filesMetadata.length}`);

    console.log('📝 Arquivos incluídos:');
    filesMetadata.forEach(file => {
      console.log(`- ${file.name} (${file.file_type}) - Última modificação: ${file.ultimaModificacao}`);
    });

  } catch (error) {
    console.error('❌ Erro ao gerar metadados:', error);
    process.exit(1);
  }
}

// Executa a geração de metadados
generateMetadata();

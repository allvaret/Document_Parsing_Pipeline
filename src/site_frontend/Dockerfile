# Usamos a imagem oficial do Node leve
FROM node:24-slim

# Define a pasta de trabalho dentro do container
WORKDIR /app

# Copia os arquivos de dependências primeiro
COPY package*.json ./

# Instala as dependências dentro do container
RUN npm install

# Copia todo o restante dos arquivos do projeto
COPY . .

# Expõe a porta padrão onde o Vite roda
EXPOSE 5173

# Comando para iniciar o servidor de desenvolvimento liberando acesso externo
CMD ["npm", "run", "dev", "--", "--host"]
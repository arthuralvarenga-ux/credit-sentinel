# Script de Deploy Automático para o seu GitHub (PowerShell / Windows)
param (
    [Parameter(Mandatory=$true)]
    [string]$RepoUrl
)

git init
git branch -M main
git add .
git commit -m "feat: implanta motor Early Warning de Risco de Crédito Privado (Watchlist 265 emissores)"
git remote remove origin 2>$null
git remote add origin $RepoUrl
git push -u origin main
Write-Host "✅ Projeto publicado com sucesso no GitHub! Acesse a aba 'Actions' do seu repositório para ativar." -ForegroundColor Green

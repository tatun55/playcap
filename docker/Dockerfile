# Shayde Playwright with Japanese Fonts
FROM mcr.microsoft.com/playwright:v1.48.0-noble

# Install font tools and Japanese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create font directories
RUN mkdir -p /usr/share/fonts/inter /usr/share/fonts/source-han-sans /usr/share/fonts/windows-style /usr/share/fonts/custom

# Download Inter (Google Fonts) - Best SF Pro alternative for Latin/English
# Full weight coverage: 100-900 (Thin to Black)
# Most popular open-source UI font, very close to Apple's San Francisco
RUN curl -fsSL -o /tmp/inter.zip \
    "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip" && \
    unzip -j /tmp/inter.zip "Inter-4.0/InterVariable.ttf" -d /usr/share/fonts/inter/ && \
    unzip -j /tmp/inter.zip "Inter-4.0/InterVariable-Italic.ttf" -d /usr/share/fonts/inter/ && \
    rm -f /tmp/inter.zip

# Download Source Han Sans JP Variable Font (Adobe) - Mac-style Japanese font
# Variable font supports weight range 250-900 (similar to Hiragino Sans)
# This is the closest open-source equivalent to Mac's Hiragino
RUN curl -fsSL -o /tmp/source-han-sans-vf.zip \
    "https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansJP-VF.otf.zip" && \
    unzip -o /tmp/source-han-sans-vf.zip -d /usr/share/fonts/source-han-sans/ && \
    rm -f /tmp/source-han-sans-vf.zip

# Also download static weights for fallback compatibility
RUN curl -fsSL -o /tmp/source-han-sans.zip \
    "https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansJP.zip" && \
    unzip -j /tmp/source-han-sans.zip "OTF/Japanese/*.otf" -d /usr/share/fonts/source-han-sans/ || \
    unzip -j /tmp/source-han-sans.zip "*.otf" -d /usr/share/fonts/source-han-sans/ || true && \
    rm -f /tmp/source-han-sans.zip

# Download BIZ UDGothic - Windows-style Japanese font (free from Google Fonts)
RUN curl -fsSL -o /tmp/bizudgothic.zip \
    "https://github.com/googlefonts/morisawa-biz-ud-gothic/releases/download/v1.05/BIZUDGothic.zip" && \
    unzip -j /tmp/bizudgothic.zip "*.ttf" -d /usr/share/fonts/windows-style/ || true && \
    rm -f /tmp/bizudgothic.zip

# Update font cache
RUN fc-cache -fv

# Verify fonts are installed
RUN fc-list | grep -E "(Inter|Source Han Sans|BIZ)" || echo "Some fonts may not be installed"

EXPOSE 3000

CMD ["npx", "playwright", "run-server", "--port", "3000", "--host", "0.0.0.0"]

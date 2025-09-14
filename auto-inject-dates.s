#!/bin/bash

echo "🚀 Автоматическая вставка скриптов обновления дат..."

# Московская дата и время
MOSCOW_DATE=$(TZ=Europe/Moscow date +"%Y-%m-%d")
MOSCOW_DATETIME="${MOSCOW_DATE}T01:00:00+03:00"

echo "Московская дата: $MOSCOW_DATE"
echo "Московское время: $MOSCOW_DATETIME"

# JavaScript код для вставки
cat > temp_script.html << 'EOF'

<script>
// Обновление дат в московском времени - Авто-инжект
(function() {
    const moscowTime = new Date().toLocaleString("en-US", {timeZone: "Europe/Moscow"});
    const moscowDate = new Date(moscowTime).toISOString().split('T')[0];
    const moscowDateTime = moscowDate + 'T01:00:00+03:00';
    
    // Обновить/создать article:modified_time
    let metaModified = document.querySelector('meta[property="article:modified_time"]');
    if (!metaModified) {
        metaModified = document.createElement('meta');
        metaModified.setAttribute('property', 'article:modified_time');
        document.head.appendChild(metaModified);
    }
    metaModified.setAttribute('content', moscowDateTime);
    
    // Обновить/создать article:published_time
    let metaPublished = document.querySelector('meta[property="article:published_time"]');
    if (!metaPublished) {
        metaPublished = document.createElement('meta');
        metaPublished.setAttribute('property', 'article:published_time');
        metaPublished.setAttribute('content', moscowDateTime);
        document.head.appendChild(metaPublished);
    }
    
    // Обновить JSON-LD Schema
    document.querySelectorAll('script[type="application/ld+json"]').forEach(script => {
        try {
            const data = JSON.parse(script.textContent);
            if (data.dateModified) data.dateModified = moscowDate;
            if (data.datePublished && !data.originalDatePublished) {
                data.originalDatePublished = data.datePublished;
                data.datePublished = moscowDate;
            }
            script.textContent = JSON.stringify(data, null, 2);
        } catch(e) {}
    });
    
    // Добавить microdata для поисковиков
    if (!document.querySelector('[itemprop="dateModified"]')) {
        const timeEl = document.createElement('time');
        timeEl.setAttribute('datetime', moscowDateTime);
        timeEl.setAttribute('itemprop', 'dateModified');
        timeEl.style.display = 'none';
        timeEl.textContent = moscowDate;
        document.body.appendChild(timeEl);
    }
})();
</script>
EOF

# Обработать все HTML файлы
find . -name "*.html" -type f | while read file; do
    echo "Обрабатываем: $file"
    
    # Проверить, есть ли уже скрипт
    if ! grep -q "Авто-инжект" "$file"; then
        # Добавить meta-теги в head если их нет
        if ! grep -q 'article:modified_time' "$file"; then
            sed -i '/<meta name="viewport"/a <meta property="article:modified_time" content="'"$MOSCOW_DATETIME"'">' "$file"
        fi
        
        if ! grep -q 'article:published_time' "$file"; then
            sed -i '/<meta property="article:modified_time"/a <meta property="article:published_time" content="'"$MOSCOW_DATETIME"'">' "$file"
        fi
        
        # Добавить скрипт перед </body>
        if grep -q "</body>" "$file"; then
            sed -i 's|</body>|'"$(cat temp_script.html | tr '\n' '\r')"'</body>|' "$file"
            sed -i 's/\r/\n/g' "$file"
            echo "✅ Скрипт добавлен в $file"
        fi
    else
        echo "⏭️  Скрипт уже есть в $file"
    fi
    
    # Обновить существующие даты
    sed -i 's/<meta property="article:modified_time" content="[^"]*"/<meta property="article:modified_time" content="'"$MOSCOW_DATETIME"'"/g' "$file"
    sed -i 's/"dateModified": "[^"]*"/"dateModified": "'"$MOSCOW_DATE"'"/g' "$file"
done

# Обновить sitemap.xml  
if [ -f "sitemap.xml" ]; then
    sed -i 's/<lastmod>[^<]*<\/lastmod>/<lastmod>'"$MOSCOW_DATE"'<\/lastmod>/g' sitemap.xml
    echo "✅ Sitemap обновлен"
fi

# Очистка
rm temp_script.html

echo "🎉 Готово! Все HTML файлы обновлены с автоматическими скриптами дат."
echo "📅 Теперь даты будут обновляться автоматически каждый день в браузере пользователей."

<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" 
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="xs tei">
    
    <xsl:output method="xml" encoding="UTF-8" indent="yes"/>
    
    <!-- Paramètres à passer lors de l'exécution -->
    <xsl:param name="filename" select="'Unknown_File.xml'"/>
    
    <!-- Variables globales pour l'auteur et le titre -->
    <xsl:variable name="author-code">
        <xsl:choose>
            <xsl:when test="contains($filename, '_')">
                <xsl:value-of select="translate(substring(substring-before($filename, '_'), 1, 3),
                                                'abcdefghijklmnopqrstuvwxyz',
                                                'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:value-of select="translate(substring(substring-before($filename, '.xml'), 1, 3),
                                                'abcdefghijklmnopqrstuvwxyz',
                                                'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:variable>
    
    <xsl:variable name="title-code">
        <xsl:choose>
            <xsl:when test="contains($filename, '_')">
                <xsl:variable name="title-part" select="substring-before(substring-after($filename, '_'), '.xml')"/>
                <!-- Extraire uniquement les lettres majuscules présentes dans le titre -->
                <!-- exemple: AbregeViePeintres -> AVP -->
                <xsl:variable name="uppercase" select="translate($title-part,
                                                 'abcdefghijklmnopqrstuvwxyz0123456789-_ .,;:!()[]{}?&quot;',
                                                 '')"/>
                <!-- Enlever ATIR du titre si présent -->
                <xsl:value-of select="translate($uppercase, 'ATIR', '')"/>
            </xsl:when>
            <xsl:otherwise/>
        </xsl:choose>
    </xsl:variable>
    
    <!-- Template par défaut : copie identique -->
    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
    
    <!-- Template pour les balises <p> sans xml:id -->
    <xsl:template match="tei:p[not(@xml:id)]">
        <xsl:copy>
            <!-- Ajouter l'attribut xml:id -->
            <xsl:attribute name="xml:id">
                <xsl:call-template name="generate-id"/>
            </xsl:attribute>
            
            <!-- Copier les autres attributs et le contenu -->
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
    
    <!-- Template nommé pour générer l'ID -->
    <xsl:template name="generate-id">
        <!-- Code auteur -->
        <xsl:value-of select="$author-code"/>
        
        <!-- Code titre -->
        <xsl:if test="string-length($title-code) &gt; 0">
            <xsl:text>_</xsl:text>
            <xsl:value-of select="$title-code"/>
        </xsl:if>
        
        <!-- IDs des parents (du plus extérieur au plus proche) -->
        <xsl:for-each select="ancestor::*[@xml:id]">
            <!-- Trier par profondeur (nombre d'ancêtres) pour envoyer l'ancêtre le plus extérieur en premier -->
            <xsl:sort select="count(ancestor::*)" data-type="number" order="ascending"/>
            <xsl:text>_</xsl:text>
            <xsl:value-of select="@xml:id"/>
        </xsl:for-each>
        
        <!-- Numéro du paragraphe -->
        <xsl:text>_P</xsl:text>
        <xsl:call-template name="paragraph-number"/>
    </xsl:template>
    
    <!-- Template pour calculer le numéro du paragraphe -->
    <xsl:template name="paragraph-number">
        <!-- Trouver le div parent le plus proche -->
        <xsl:variable name="parent-div" select="ancestor::*[substring(local-name(),1,3) = 'div'][1]"/>
        
        <xsl:choose>
            <!-- Si on a un div parent -->
            <xsl:when test="$parent-div">
                <!-- Compter les <p> précédents dont le div parent le plus proche est le même -->
                <xsl:value-of select="count(preceding::tei:p[generate-id(ancestor::*[substring(local-name(),1,3) = 'div'][1]) = generate-id($parent-div)]) + 1"/>
            </xsl:when>
            <!-- Sinon, compter tous les <p> précédents sans div parent -->
            <xsl:otherwise>
                <!-- Pour éviter un prédicat complexe, calculer en deux variables -->
                <xsl:variable name="prev-no-div" select="preceding::tei:p[not(ancestor::*[substring(local-name(),1,3) = 'div'])]"/>
                <xsl:variable name="ancp-no-div" select="ancestor::tei:p[not(ancestor::*[substring(local-name(),1,3) = 'div'])]"/>
                <xsl:value-of select="count($prev-no-div) + count($ancp-no-div) + 1"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
</xsl:stylesheet>

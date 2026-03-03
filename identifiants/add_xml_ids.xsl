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
                <!-- Extraire uniquement les lettres majuscules (et maintenant les chiffres) du titre -->
                <!-- exemple: AbregeViePeintres -> AVP ; Ex1 -> EX1 -->
                <!-- on ne retire plus les chiffres, seulement la ponctuation et les lettres minuscules -->
                <xsl:variable name="uppercase" select="translate($title-part,
                                                 'abcdefghijklmnopqrstuvwxyz-_ .,;:!()[]{}?&quot;',
                                                 '')"/>
                <!-- Ne supprimer "ATIR" que lorsqu'il apparaît comme séquence complète -->
                <xsl:choose>
                    <xsl:when test="contains($uppercase,'ATIR')">
                        <xsl:value-of select="concat(substring-before($uppercase,'ATIR'),
                                                     substring-after($uppercase,'ATIR'))"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="$uppercase"/>
                    </xsl:otherwise>
                </xsl:choose>
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
    
    <!-- Template pour les balises <p> : on ne crée un `xml:id` que si l'élément
         n'en possède pas déjà. Ainsi on ne modifie pas les IDs existants
         lors de relances du script. -->
    <xsl:template match="tei:p[not(@xml:id) and not(ancestor::tei:teiHeader) and not(ancestor::tei:figure)]"><!-- si p pas dans teiheader et pas dans figure-->
        <!-- recréer le paragraphe depuis zéro afin de pouvoir contrôler les attributs -->
        <xsl:element name="{name()}" namespace="{namespace-uri()}">
            <!-- nouvel identifiant unique généré -->
            <xsl:attribute name="xml:id">
                <xsl:call-template name="generate-id"/>
            </xsl:attribute>
            <!-- recopier les autres attributs sans xml:id et le contenu -->
            <xsl:apply-templates select="@*[name()!='xml:id']|node()"/>
        </xsl:element>
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
        
        <!-- IDs des parents (du plus extérieur au plus proche)
             On inclut soit @xml:id s'il existe, soit pour les div simples
             on utilise l'attribut @type comme identifiant (pour numéroter en continu).
        -->
        <xsl:for-each select="ancestor::*[@xml:id or (starts-with(local-name(.),'div') and @type)]">
            <!-- Trier par profondeur pour envoyer l'ancêtre le plus extérieur en premier -->
            <xsl:sort select="count(ancestor::*)" data-type="number" order="ascending"/>
            <xsl:text>_</xsl:text>
            <xsl:choose>
                <xsl:when test="@xml:id">
                    <xsl:value-of select="@xml:id"/>
                </xsl:when>
                <xsl:when test="starts-with(local-name(.),'div') and @type">
                    <xsl:value-of select="@type"/>
                </xsl:when>
                <xsl:otherwise>
                    <!-- fallback: use generate-id to avoid empty output -->
                    <xsl:value-of select="generate-id()"/>
                </xsl:otherwise>
            </xsl:choose>
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
                <!-- Si le div parent a un @xml:id, compter les <p> précédents dans le même div (par id) -->
                <xsl:choose>
                    <xsl:when test="$parent-div/@xml:id">
                        <xsl:value-of select="count(preceding::tei:p[ancestor::*[substring(local-name(),1,3) = 'div'][1][@xml:id = $parent-div/@xml:id]]) + 1"/>
                    </xsl:when>
                    <!-- Sinon, si le div parent est un "div" simple ou un div4 et div5 qui ne possède pas @xml:id et possède @type, compter en continu
                         pour tous les <p> précédents dont le div le plus proche a le même @type -->
                    <xsl:when test="local-name($parent-div) = 'div' and $parent-div/@type">
                        <xsl:value-of select="count(preceding::tei:p[ancestor::*[local-name() = 'div'][1][@type = $parent-div/@type]]) + 1"/>
                    </xsl:when>
                    <!-- fallback: revenir à la méthode par generate-id du parent-div -->
                    <xsl:otherwise>
                        <xsl:value-of select="count(preceding::tei:p[generate-id(ancestor::*[substring(local-name(),1,3) = 'div'][1]) = generate-id($parent-div)]) + 1"/>
                    </xsl:otherwise>
                </xsl:choose>
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

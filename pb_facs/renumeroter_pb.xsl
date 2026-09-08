<xsl:stylesheet version="2.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="tei xs">
    
    <xsl:output method="xml" indent="no" encoding="UTF-8"/>
    
    <!-- copie identité -->
    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
    
    <!--  Template spécifique pour ajouter le xi:include IndexOeuvres à la fin de sourceDesc  -->
    <xsl:template match="tei:sourceDesc">
        <sourceDesc xmlns="http://www.tei-c.org/ns/1.0">
            <!--   Copier les attributs existants (s'il y en a)   -->
            <xsl:apply-templates select="@*"/>
            <!--   Copier le contenu existant (bibl, msDesc, etc.), en excluant un éventuel xi:include IndexOeuvres déjà présent   -->
            <xsl:apply-templates select="node()[not(local-name()='include' and contains(@href, 'IndexOeuvres'))][not(local-name()='listObject')]"/>
            
            <!--   Ajouter l'inclusion IndexOeuvres à la fin   -->
            <xsl:text> </xsl:text>
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexOeuvres.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
        </sourceDesc>
    </xsl:template>
    <!-- Template spécifique pour recréer profileDesc avec xi:include -->
    <xsl:template match="tei:profileDesc">
        <profileDesc xmlns="http://www.tei-c.org/ns/1.0">
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexPersonnes.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
            <xsl:text>
         </xsl:text>
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexLieux.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
        </profileDesc>
    </xsl:template>
    
    <!-- décalage à partir de n="69" et pour tous les pb suivants -->
    <xsl:template match="tei:pb[xs:integer(@n) >= 17]">
        <xsl:copy>
            <xsl:apply-templates select="@*[not(name()='n')]"/>
            <xsl:attribute name="n" select="xs:integer(@n) - 16"/>
        </xsl:copy>
    </xsl:template>
    
</xsl:stylesheet>
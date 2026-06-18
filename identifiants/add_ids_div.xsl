<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:tei="http://www.tei-c.org/ns/1.0" version="2.0" exclude-result-prefixes="tei">
    <xsl:output method="xml" indent="yes" omit-xml-declaration="no"/>
    
    <!--  Template de copie par défaut pour tous les éléments et attributs  -->
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
    <!--  Template spécifique pour les div1 TEI  -->
    <xsl:template match="tei:div1">
        <xsl:variable name="parent-id" select="parent::tei:body/@xml:id"/>
        <xsl:variable name="position" select="count(preceding-sibling::tei:div1) + 1"/>
        <div1 xmlns="http://www.tei-c.org/ns/1.0">
            <!--  Ajouter xml:id (par exemple L1, L2, etc.)  -->
            <xsl:attribute name="xml:id">
                <xsl:value-of select="concat('L', $position)"/>
            </xsl:attribute>
            <!--  Ajouter type="chapitre"  -->
            <xsl:attribute name="type">livre</xsl:attribute>
            <!--  Ajouter n avec la position  -->
            <xsl:attribute name="n">
                <xsl:value-of select="$position"/>
            </xsl:attribute>
            <!--  Copier les attributs existants (s'il y en a)  -->
            <xsl:apply-templates select="@*"/>
            <!--  Copier le contenu  -->
            <xsl:apply-templates select="node()"/>
        </div1>
    </xsl:template>
    
    <!--  Template spécifique pour les div2 TEI  -->
    <xsl:template match="tei:div2">
        <xsl:variable name="parent-id" select="parent::tei:div1/@xml:id"/>
        <xsl:variable name="position" select="count(preceding-sibling::tei:div2) + 1"/>
        <div2 xmlns="http://www.tei-c.org/ns/1.0">
            <!--  Ajouter xml:id (par exemple L1C1, L1C2, etc.)  -->
            <xsl:attribute name="xml:id">
                <xsl:value-of select="concat($parent-id, 'C', $position)"/>
            </xsl:attribute>
            <!--  Ajouter type="chapitre"  -->
            <xsl:attribute name="type">chapitre</xsl:attribute>
            <!--  Ajouter n avec la position  -->
            <xsl:attribute name="n">
                <xsl:value-of select="$position"/>
            </xsl:attribute>
            <!--  Copier les attributs existants (s'il y en a)  -->
            <xsl:apply-templates select="@*"/>
            <!--  Copier le contenu  -->
            <xsl:apply-templates select="node()"/>
        </div2>
    </xsl:template>
    
    <!--  Template spécifique pour les div3 TEI  -->
    <xsl:template match="tei:div3">
        <xsl:variable name="div1-id" select="ancestor::tei:div1/@xml:id"/>
        <xsl:variable name="div2-position" select="count(parent::tei:div2/preceding-sibling::tei:div2) + 1"/>
        <xsl:variable name="position" select="count(preceding-sibling::tei:div3) + 1"/>
        <div3 xmlns="http://www.tei-c.org/ns/1.0">
            <!--  Reconstruire l'ID complet : L1C1SC1  -->
            <xsl:attribute name="xml:id">
                <xsl:value-of select="concat($div1-id, 'C', $div2-position, 'SC', $position)"/>
            </xsl:attribute>
            <!--  Ajouter type="sous-chapitre"  -->
            <xsl:attribute name="type">sous-chapitre</xsl:attribute>
            <!--  Ajouter n avec la position  -->
            <xsl:attribute name="n">
                <xsl:value-of select="$position"/>
            </xsl:attribute>
            <!--  Copier les attributs existants (s'il y en a)  -->
            <xsl:apply-templates select="@*"/>
            <!--  Copier le contenu  -->
            <xsl:apply-templates select="node()"/>
        </div3>
    </xsl:template>
    
    <!--  Template spécifique pour les div4 TEI  -->
    <xsl:template match="tei:div4">
        <xsl:variable name="div1-id" select="ancestor::tei:div1/@xml:id"/>
        <xsl:variable name="div2-position" select="count(ancestor::tei:div2/preceding-sibling::tei:div2) + 1"/>
        <xsl:variable name="div3-position" select="count(parent::tei:div3/preceding-sibling::tei:div3) + 1"/>
        <xsl:variable name="position" select="count(preceding-sibling::tei:div4) + 1"/>
        <div4 xmlns="http://www.tei-c.org/ns/1.0">
            <!--  Reconstruire l'ID complet : L1C1SC1S1  -->
            <xsl:attribute name="xml:id">
                <xsl:value-of select="concat($div1-id, 'C', $div2-position, 'SC', $div3-position, 'S', $position)"/>
            </xsl:attribute>
            <!--  Ajouter type="section"  -->
            <xsl:attribute name="type">section</xsl:attribute>
            <!--  Ajouter n avec la position  -->
            <xsl:attribute name="n">
                <xsl:value-of select="$position"/>
            </xsl:attribute>
            <!--  Copier les attributs existants (s'il y en a)  -->
            <xsl:apply-templates select="@*"/>
            <!--  Copier le contenu  -->
            <xsl:apply-templates select="node()"/>
        </div4>
    </xsl:template>
    <!--  Template spécifique pour les div4 TEI  -->
    <xsl:template match="tei:div5">
        <xsl:variable name="div1-id" select="ancestor::tei:div1/@xml:id"/>
        <xsl:variable name="div2-position" select="count(ancestor::tei:div2/preceding-sibling::tei:div2) + 1"/>
        <xsl:variable name="div3-position" select="count(parent::tei:div3/preceding-sibling::tei:div3) + 1"/>
        <xsl:variable name="div4-position" select="count(parent::tei:div4/preceding-sibling::tei:div4) + 1"/>
        <xsl:variable name="position" select="count(preceding-sibling::tei:div5) + 1"/>
        <div5 xmlns="http://www.tei-c.org/ns/1.0">
            <!--  Reconstruire l'ID complet : L1C1SC1S1SS1  -->
            <xsl:attribute name="xml:id">
                <xsl:value-of select="concat($div1-id, 'C', $div2-position, 'SC', $div3-position, 'S', $div4-position, 'SS', $position)"/>
            </xsl:attribute>      
            <!--  Ajouter n avec la position  -->
            <xsl:attribute name="n">
                <xsl:value-of select="$position"/>
            </xsl:attribute>
            <!--  Copier les attributs existants (s'il y en a)  -->
            <xsl:apply-templates select="@*"/>
            <!--  Copier le contenu  -->
            <xsl:apply-templates select="node()"/>
        </div5>
    </xsl:template>
</xsl:stylesheet>
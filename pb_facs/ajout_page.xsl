<xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="tei">

    <xsl:output method="xml" indent="yes" omit-xml-declaration="no"/>

    <!-- paramètre pour le point de départ -->
    <xsl:param name="start" select="9"/>

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
    <xsl:template match="tei:body//tei:pb">
        <xsl:copy>
            <xsl:variable name="LienGallica">
                <xsl:text>http://gallica.bnf.fr/ark:/12148/bpt6k8703191d/</xsl:text>
            </xsl:variable>
            <xsl:apply-templates select="@*"/>
            <xsl:variable name="num">
                <xsl:number level="any" count="tei:body//tei:pb"/>
            </xsl:variable>
            <xsl:attribute name="facs">
                <xsl:value-of select="concat($LienGallica, 'f', $start + $num - 1, '.item')"/>
            </xsl:attribute>
            <xsl:apply-templates select="node()"/>
        </xsl:copy>
    </xsl:template>

    <!--Template pour les pb-->
    <!-- 
    <xsl:template match="tei:body//tei:pb">
        <xsl:copy>          
            <xsl:apply-templates select="@*"/>
            <xsl:variable name="num">
                <xsl:number level="any" count="tei:body//tei:pb"/>
            </xsl:variable>
            <xsl:attribute name="n">
                <xsl:value-of select="$start + $num - 1"/>
            </xsl:attribute>
            <xsl:apply-templates select="node()"/>
        </xsl:copy>
    </xsl:template>-->
    
    
    <!--<xsl:template match="tei:text//tei:pb">
        <xsl:copy>
            <xsl:variable name="LienINHA">
                <xsl:text>https://bibliotheque-numerique.inha.fr/idviewer/11862/</xsl:text>
            </xsl:variable>
            <xsl:apply-templates select="@*"/>
            <xsl:variable name="num">
                <xsl:number level="any" count="tei:text//tei:pb"/>
            </xsl:variable>
            <xsl:attribute name="facs">
                <xsl:value-of select="concat($LienINHA, $start + $num - 1)"/>
            </xsl:attribute>
            <xsl:apply-templates select="node()"/>
        </xsl:copy>
        
    </xsl:template>-->
    
</xsl:stylesheet>

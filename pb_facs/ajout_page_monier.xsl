<xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="tei">

    <xsl:output method="xml" indent="yes" omit-xml-declaration="no"/>

    <xsl:variable name="ark">
        <xsl:text>bpt6k6557500p</xsl:text>
    </xsl:variable>

    <!-- paramètre pour le point de départ -->
    <xsl:param name="start" select="61"/>

    <!-- Template identité par défaut -->
    <xsl:template match="@* | node()">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
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

    <!-- Template pour les pb -->
    <xsl:template match="tei:body//tei:pb">
        <xsl:copy>
            <!-- Correction 1 : interpoler $ark avec concat() -->
            <xsl:variable name="LienGallica"
                select="concat('http://gallica.bnf.fr/ark:/12148/', $ark, '/')"/>
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

    
    <!--
    <xsl:template match="tei:text//tei:pb">
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
        
    </xsl:template>
    -->
    
</xsl:stylesheet>

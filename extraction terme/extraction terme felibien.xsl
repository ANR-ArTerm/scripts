<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  exclude-result-prefixes="tei">
  
  <xsl:output method="text" encoding="UTF-8"/>
  
  <!-- Point d'entrée -->
  <xsl:template match="/">
    <xsl:apply-templates
      select="//tei:div1[@type='dictionnaire']//tei:p/tei:hi[@rend='capitals'][1]"/>
  </xsl:template>
  
  <!-- Terme -->
  <xsl:template match="tei:hi[@rend='capitals']">
    <xsl:value-of select="normalize-space(.)"/>
    <xsl:text>&#10;</xsl:text>
  </xsl:template>
  
</xsl:stylesheet>
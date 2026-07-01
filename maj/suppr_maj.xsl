<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="xs tei" version="2.0">
<xsl:output method="xml" encoding="UTF-8" indent="no" omit-xml-declaration="no"/>
<!--  ============================================================
         VARIABLES GLOBALES
    ============================================================  -->
<xsl:variable name="UC" select="'ABCDEFGHIJKLMNOPQRSTUVWXYZÀÂÄÉÈÊËÎÏÔÙÛÜ'"/>
<xsl:variable name="LC" select="'abcdefghijklmnopqrstuvwxyzàâäéèêëîïôùûü'"/>
<!--  Chiffres romains : corps en majuscules + suffixe ordinal optionnel
         en minuscules (e, è, er, ème, ième)  -->
<xsl:variable name="ROMAN" select="'^(M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3}))(e|è|er|ème|ieme|ième)?$'"/>
<!--  Regex qui capture un mot commençant par une majuscule  -->
<xsl:variable name="MOT_MAJUSCULE" select="'[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ][A-Za-zÀÂÄÉÈÊËÎÏÔÙÛÜàâäéèêëîïôùûü]*'"/>
<!--  ============================================================
         TERMES À CONSERVER (liste blanche)

         Deux variables complémentaires :
         - TERMES_MULTI : séquences de plusieurs mots — testées sur
           le texte complet autour du mot courant.
         - TERMES_MONO  : mots simples — testés sur le mot seul.

         Pour ajouter un terme : l'insérer dans la liste en séparant
         les alternatives par | dans la regex.
         Les termes multi-mots doivent figurer dans TERMES_MULTI,
         les mots simples dans TERMES_MONO.
    ============================================================  -->
<!--  Séquences multi-mots : la regex est testée sur le texte à
         partir de la position du mot courant. On utilise \s+ entre
         les tokens pour accepter tout type d'espace.  -->
<xsl:variable name="TERMES_MULTI" select="'^(Vostra\s+Signoria|Altezza\s+Vostra|Sua\s+Signoria|Sua\s+Altezza)'"/>
<!--  Mots simples : testés directement sur $mot (correspondance exacte).  -->
<xsl:variable name="TERMES_MONO" select="'^(VS|SA|Roi|Reine|Re|Rei|Monseigneur|Archev[eê]que|Grandduc|Nil|Illustrissima|Signoria|Vostra|Altezza)$'"/>
<!--  ============================================================
         RÈGLE IDENTITÉ
    ============================================================  -->
<xsl:template match="@* | node()">
<xsl:copy>
<xsl:apply-templates select="@* | node()"/>
</xsl:copy>
</xsl:template>
<!--  ============================================================
         TEIHEADER : nœuds texte recopiés sans modification.
    ============================================================  -->
<xsl:template match="*[local-name() = 'teiHeader']//text()">
<xsl:value-of select="."/>
</xsl:template>
 <!--  ============================================================
       SOURCEDESC : ajout de xi:include IndexOeuvres
  ============================================================  -->
    <xsl:template match="*[local-name() = 'sourceDesc']">
        <xsl:copy>
            <xsl:apply-templates select="@*"/>
            <xsl:apply-templates select="node()[ not(local-name() = 'include' and contains(@href, 'IndexOeuvres')) ][ not(local-name() = 'listObject') ]"/>
            <xsl:text> </xsl:text>
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexOeuvres.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
        </xsl:copy>
    </xsl:template>
    <!--  ============================================================
       PROFILEDESC : reconstruction avec xi:include
  ============================================================  -->
    <xsl:template match="*[local-name() = 'profileDesc']">
        <xsl:copy>
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexPersonnes.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
            <xsl:text> </xsl:text>
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexLieux.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
        </xsl:copy>
    </xsl:template><!--  ============================================================
         BALISES PROTÉGÉES DANS LE BODY
    ============================================================  -->
<xsl:template match="*[ local-name() = 'persName' or local-name() = 'placeName' or local-name() = 'objectName' or local-name() = 'date' or local-name() = 'item' or (local-name() = 'hi' and @rend = 'capitals') ]">
<xsl:copy>
<xsl:apply-templates select="@*"/>
<xsl:value-of select="."/>
</xsl:copy>
</xsl:template>
<!--  ============================================================
         NŒUDS TEXTE CIBLES : dans <p> et <l>, hors balises protégées
         et hors teiHeader.
    ============================================================  -->
<xsl:template match=" text()[ (ancestor::*[local-name()='p'] or ancestor::*[local-name()='l']) and not(ancestor::*[local-name()='teiHeader']) and not( ancestor::*[local-name()='persName'] or ancestor::*[local-name()='placeName'] or ancestor::*[local-name()='objectName'] or ancestor::*[local-name()='date'] or ancestor::*[local-name()='hi' and @rend='capitals'] ) ]">
<xsl:variable name="ancetre_cible" select="(ancestor::*[local-name()='p'] | ancestor::*[local-name()='l'])[last()]"/>
<xsl:variable name="est_debut_balise" as="xs:boolean" select="not( current()/preceding::text()[ ancestor::*[. is $ancetre_cible] ][ not( ancestor::*[local-name()='persName'] or ancestor::*[local-name()='placeName'] or ancestor::*[local-name()='objectName'] or ancestor::*[local-name()='date'] or ancestor::*[local-name()='hi' and @rend='capitals'] ) and normalize-space(.) != '' ] )"/>
<xsl:call-template name="traiter_texte">
<xsl:with-param name="texte" select="string(.)"/>
<xsl:with-param name="est_debut" select="$est_debut_balise"/>
</xsl:call-template>
</xsl:template>
<!--  ============================================================
         TRAITEMENT DU TEXTE PAR TOKENISATION (analyze-string)
    ============================================================  -->
<xsl:template name="traiter_texte">
<xsl:param name="texte" as="xs:string"/>
<xsl:param name="est_debut" as="xs:boolean"/>
<xsl:variable name="premiere_pos_utile" as="xs:integer" select="string-length($texte) - string-length(replace($texte, '^\s+', '')) + 1"/>
<xsl:analyze-string select="$texte" regex="{$MOT_MAJUSCULE}">
<xsl:matching-substring>
<xsl:variable name="mot" select="."/>
<xsl:variable name="pos_dans_texte" select="string-length(substring-before($texte, $mot)) + 1"/>
<xsl:variable name="gauche" select="substring($texte, 1, $pos_dans_texte - 1)"/>
<!--  Texte à partir du mot courant (pour tester les termes multi-mots)  -->
<xsl:variable name="depuis_mot" select="substring($texte, $pos_dans_texte)"/>
<xsl:variable name="conserver" as="xs:boolean">
<xsl:choose>
<!--  Règle 1 : mot d'une seule lettre (ex. initiales, O, Y…)  -->
<xsl:when test="string-length($mot) = 1">
<xsl:value-of select="true()"/>
</xsl:when>
<!--  Règle 2 : chiffre romain  -->
<xsl:when test="matches($mot, $ROMAN)">
<xsl:value-of select="true()"/>
</xsl:when>
<!--  Règle 3 : terme mono-mot de la liste blanche  -->
<xsl:when test="matches($mot, $TERMES_MONO)">
<xsl:value-of select="true()"/>
</xsl:when>
<!--  Règle 4 : début d'un terme multi-mots de la liste blanche.
                             On teste si le texte à partir du mot courant commence
                             par une des séquences protégées.  -->
<xsl:when test="matches($depuis_mot, $TERMES_MULTI)">
<xsl:value-of select="true()"/>
</xsl:when>
<!--  Règle 5 : première lettre du <p>/<l>  -->
<xsl:when test="$est_debut and $pos_dans_texte = $premiere_pos_utile">
<xsl:value-of select="true()"/>
</xsl:when>
<!--  Règle 6 : précédé d'une ponctuation forte  -->
<xsl:when test="matches($gauche, '[.!?]\s*$')">
<xsl:value-of select="true()"/>
</xsl:when>
<xsl:otherwise>
<xsl:value-of select="false()"/>
</xsl:otherwise>
</xsl:choose>
</xsl:variable>
<xsl:choose>
<xsl:when test="$conserver">
<xsl:value-of select="$mot"/>
</xsl:when>
<xsl:otherwise>
<xsl:value-of select="concat(translate(substring($mot,1,1), $UC, $LC), substring($mot, 2))"/>
</xsl:otherwise>
</xsl:choose>
</xsl:matching-substring>
<xsl:non-matching-substring>
<xsl:value-of select="."/>
</xsl:non-matching-substring>
</xsl:analyze-string>
</xsl:template>
</xsl:stylesheet>
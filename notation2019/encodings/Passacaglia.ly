\version "2.20.0"
% automatically converted from MEI by mei2ly.xsl

\header {
  tagline = "automatically converted from MEI with mei2ly.xsl and engraved with Lilypond"
}

mdivA_staffA = {
  \set Staff.clefGlyph = #"clefs.F" \set Staff.clefPosition = #2 \set Staff.clefTransposition = #0 \set Staff.middleCPosition = #6 \set Staff.middleCClefPosition = #6 \key f\major
  \time 2/4 
  << { d4 r4 } >> %1
  << { cis!4 r4 } >> %2
  << { b4 r4 } >> %3
  << { aes!4 r4 } >> %4
  << { f4 r4 } >> %5
  << { e4 r4 } >> %6
  << { a4 r4 } >> %7
  << { d4 r4 } >> %8
}


\score { <<
\new StaffGroup <<
 \set StaffGroup.systemStartDelimiter = #'SystemStartBar
 \new Staff = "staff 1" {
 \override Staff.StaffSymbol.line-count = #5
    \set Staff.autoBeaming = ##f 
    \set tieWaitForNote = ##t
 \key f\major
\time 2/4 \mdivA_staffA }
>>
>>
\layout {
}
}


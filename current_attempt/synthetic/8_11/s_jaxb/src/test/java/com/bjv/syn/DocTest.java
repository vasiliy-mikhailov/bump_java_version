package com.bjv.syn;
import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.assertEquals;
class DocTest { @Test void roundtrip() { Doc d = new Doc(); d.setTitle("hi"); assertEquals("hi", d.getTitle()); } }

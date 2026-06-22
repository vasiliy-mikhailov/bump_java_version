package com.bjv.syn;
import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.assertEquals;
class PersonTest { @Test void accessors() { Person p = new Person("Ada", 36); assertEquals("Ada", p.getName()); assertEquals(36, p.getAge()); } }

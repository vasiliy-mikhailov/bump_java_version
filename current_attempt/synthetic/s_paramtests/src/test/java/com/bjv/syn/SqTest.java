package com.bjv.syn;
import org.junit.jupiter.params.ParameterizedTest; import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.assertTrue;
class SqTest { @ParameterizedTest @ValueSource(ints = {1,2,3,4,5}) void nonNeg(int n) { assertTrue(new Sq().sq(n) >= 0); } }

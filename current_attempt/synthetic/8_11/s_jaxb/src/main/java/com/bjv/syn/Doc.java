package com.bjv.syn;
import javax.xml.bind.annotation.XmlRootElement;   // in JDK 8, REMOVED in JDK 11 (needs jaxb-api)
import javax.xml.bind.annotation.XmlElement;

@XmlRootElement
public class Doc {
    private String title;
    @XmlElement public String getTitle() { return title; }
    public void setTitle(String t) { this.title = t; }
}
